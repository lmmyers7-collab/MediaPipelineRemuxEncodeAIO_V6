# V5 UI Implementation — Stage 2 (Claude)

**Owner:** Claude
**Depends on:** `V5_UI_IMPL_STAGE1_CODEX.md` — all four tasks complete and verified. Do not begin Stage 2 until the Stage 1 completion checklist is fully checked.
**Design authority:** `Docs/DesktopApp/docs/V5_UI_DESIGN_REFERENCE.md`

---

## Context

Stage 1 (Codex) made all the mechanical text changes: nav labels, panel headings, button labels, and `data-panel-type` declarations. This stage handles everything that requires reading and judgment:

1. **CSS token system** — define the design reference's named tokens in `:root`, then migrate all hardcoded values to use them
2. **Visual personality** — apply the structural rules from Section 1 and 7 of the design reference (border-radius, nav active state, button tiers, table headers)
3. **Spacing tokens** — add the spacing scale to `:root` (full migration is deferred to Stage 3)
4. **Uncertain panel classification** — resolve any `<!-- REVIEW: panel type uncertain -->` flags Codex left behind
5. **Inventory and log discipline** — confirm no new DOM IDs or exports were introduced; append required log entries

**File paths used throughout this document:**

```
HTML   = DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html
CSS    = DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css
JS_DIR = DesktopApp\mediapipeline_desktop_app\ui_web\static\assets
```

---

## Task 1 — Gate check: verify Stage 1 is complete

Run all of these before touching `styles.css`. If any check fails, stop and complete Stage 1 first.

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# Task 1 gate — nav labels
Select-String -Path $html -Pattern 'data-page="home">Dashboard<'     # must return 1
Select-String -Path $html -Pattern 'data-page="live">Telemetry<'     # must return 1
Select-String -Path $html -Pattern 'data-page="reports">Reports<'    # must return 1
Select-String -Path $html -Pattern 'data-page="network">Workers<'    # must return 1

# Task 2 gate — panel heading sample
Select-String -Path $html -Pattern '<h2>System Readiness</h2>'       # must return 1
Select-String -Path $html -Pattern '<h2>Start Pipeline</h2>'         # must return 1
Select-String -Path $html -Pattern '<h2>Settings Editor</h2>'        # must return 1
Select-String -Path $html -Pattern '<h2>Output Files</h2>'           # must return 1

# Task 3 gate — button labels
Select-String -Path $html -Pattern '>Save Settings<'                 # must return 1
Select-String -Path $html -Pattern '>Submit Rename to Backend<'      # must return 1
Select-String -Path $html -Pattern '>Preview Rename Plan<'           # must return 1

# Task 4 gate — all panels typed
$untyped = (Select-String -Path $html -Pattern '<section class="panel">' |
  Where-Object { $_.Line -notmatch 'data-panel-type=' }).Count
Write-Host "Untyped panels: $untyped"   # must be 0

# Record uncertain panel count from Stage 1 — this is the Stage 2 review queue
$uncertain = (Select-String -Path $html -Pattern 'REVIEW: panel type uncertain').Count
Write-Host "Uncertain panels flagged by Codex: $uncertain"
```

All nav checks must return exactly 1. All heading checks must return exactly 1. Untyped panels must be 0. Proceed only when all pass.

---

## Task 2 — CSS audit (read before touching anything)

**Read `styles.css` in full before making any changes.** The following is a pre-completed audit based on the current file — verify these findings still hold before proceeding, as Codex may have touched the file.

### Audit findings (current state as of initial read)

**A. Current :root tokens (ad-hoc system — being replaced)**

```css
color-scheme: dark;
--bg:       #0e151d   /* main canvas background */
--surface:  #121d27   /* panel / sidebar surface */
--surface-2:#172635   /* raised surface */
--line:     #2a4054   /* borders */
--text:     #e8f1f7   /* primary text (near-white) */
--muted:    #8fa5b7   /* de-emphasized labels */
--accent:   #36d17d   /* green — action / active state */
--accent-2: #65a7ff   /* blue — secondary accent */
--warn:     #ffc857   /* amber warning */
--danger:   #ff6b7a   /* red danger */
```

None of the design reference token names (`--grey-*`, `--blue-*`, `--text-*`, `--space-*`, `--shadow-*`) currently exist.

**B. Raw hex values in the file (unique)**

```
#0e151d  #0f1923  #121d27  #172635  #132131  #163525
#1a2938  #253342  #1d3550  #133459  #26394a  #2a4054
#123823  #1f7f4a  #3f3311  #a3742b  #4a1d27  #5b2a36
#2a141b  #d3e1ec  #a8f0c4  #ffc1c9  #ffe29a  #b9d7ff
#bfdbfe  #ffd88a
```

Total: 26 unique hardcoded hex values. All must be replaced with design reference tokens.

**C. rgba() calls (translucent blends — require special handling)**

```
rgba(42, 64, 84, 0.72)       — table cell border-bottom
rgba(54, 209, 125, 0.16)     — selected row background
rgba(101, 167, 255, 0.08)    — hover row background
rgba(101, 167, 255, 0.14)    — focus-visible row background
rgba(101, 167, 255, 0.65)    — focus-visible inset border
```

These are replaced in Task 4 using `color-mix()`. See the note in Task 4 about fallback.

**D. Raw font-size values**

| Raw value | Where used | Design ref token |
|---|---|---|
| `12px` | Table cells, chips, textarea, `.note`, `.form-grid label`, `.metric-label`, `.check-row`, most components | `--text-xs` |
| `13px` | `.brand-version`, `.panel-subheading h3`, `.note` (some), `.filter-field`, `.action-group-label`, `.settings-summary-grid h3` | `--text-sm` |
| `16px` | `.panel-heading h2`, `.panel-heading h3` | `--text-md` (17px) — round up |
| `18px` | `.topbar h1` | `--text-lg` (20px) — see note |
| `22px` | `.brand-name` | `--text-xl` (24px) — round up |
| `26px` | `.metric strong` | `--text-2xl` (30px) — or keep at `--text-xl`; document decision |

> **Note on topbar h1 at 18px:** The design reference specifies `--text-xl` (24px) for the page title. The current 18px is smaller. Recommendation: use `--text-lg` (20px) as a conservative step up — it is still an improvement and avoids a dramatic size jump. If `--text-xl` is chosen, verify layout doesn't break on the narrowest supported width (1120px).

> **Note on metric strong at 26px:** The design reference defines `--text-2xl` (30px) as "reserved for single-stat callouts." Metrics are exactly that — apply `--text-2xl`. If 30px breaks metric card layout, fall back to `--text-xl` (24px) and document.

**E. Color scheme**

The current implementation is dark mode (`color-scheme: dark`). The design reference was written assuming a light-mode color model (grey-50 ≈ page background, grey-900 ≈ primary text). **Recommendation: keep dark mode.** Reasons:

1. Switching to light mode is a complete visual rebuild requiring operator sign-off — out of scope for Stage 2.
2. The token *names* from the design reference can be adopted now without changing the color model.
3. The token *values* must be adapted for dark mode (see Task 3).
4. A future light-mode toggle would only redefine the `:root` values — class names and HTML are unchanged.

**F. Structural issues vs design reference**

| Property | Current | Design reference target |
|---|---|---|
| `.panel`, `.metric` `border-radius` | `8px` | `2px` |
| `.topbar` `border-radius` | `8px` | `2px` |
| `.nav-button`, `.secondary-button`, `.danger-button` `border-radius` | `8px` | `2px` |
| `.option-panel` `border-radius` | `8px` | `2px` |
| `.table-wrap` `border-radius` | `8px` | `2px` |
| `input`, `select`, `textarea` `border-radius` | `8px` | `2px` |
| `canvas` `border-radius` | `8px` | `2px` |
| Chips (`.state-pill`, `.close-readiness`, `.refresh-health`) `border-radius` | `999px` | Keep — pills/chips are correct at 999px |
| Active nav background | `#163525` (green-tinted) | Dark blue tint: `--blue-800` |
| Active nav border | `var(--accent)` (green) | `--blue-500` |
| Nav active: left accent border | None — all-sides border | Add `border-left-width: 3px` |
| `font-weight: 650` | Topbar h1 | Not a web-standard weight. Change to `600` (semibold). |
| `font-weight: 700` | Multiple elements | Keep for `.metric strong` (callout); change to `600` elsewhere per Section 3 |

---

## Task 3 — Apply the :root token block

Open `styles.css`. Replace the entire existing `:root { ... }` block (lines 1–13) with the following dark-mode token block. Do not touch any other rule yet.

```css
:root {
  color-scheme: dark;

  /* ===== GREY SCALE — cool-tinted (220°), dark-mode adapted =====
     Usage is inverted from light-mode model: grey-900 = darkest bg, grey-50 = near-white text.
     Token names match the design reference (Sections 2–4) so a future light-mode
     switch only needs to redefine these values, not any class names or markup.       */
  --grey-900: hsl(220, 15%, 8%);     /* deepest bg — main canvas */
  --grey-800: hsl(220, 13%, 12%);    /* sidebar, primary panel surface */
  --grey-700: hsl(220, 11%, 18%);    /* raised surface, option panels */
  --grey-600: hsl(220, 10%, 26%);    /* borders, dividers */
  --grey-500: hsl(220, 9%, 36%);     /* muted / inactive borders */
  --grey-400: hsl(220, 8%, 50%);     /* disabled text, muted labels */
  --grey-300: hsl(220, 7%, 62%);     /* secondary text */
  --grey-200: hsl(220, 6%, 75%);     /* body text, form values */
  --grey-100: hsl(220, 5%, 88%);     /* primary text */
  --grey-50:  hsl(220, 4%, 95%);     /* headings, near-white text */

  /* ===== BLUE — action, active state, selection ===== */
  --blue-900: hsl(215, 60%, 18%);    /* very dark blue bg — active nav */
  --blue-800: hsl(215, 55%, 28%);    /* dark blue tint — selected row bg */
  --blue-700: hsl(215, 52%, 38%);
  --blue-600: hsl(215, 50%, 48%);    /* button hover */
  --blue-500: hsl(215, 55%, 56%);    /* base — buttons, active nav border, selected row accent */
  --blue-400: hsl(215, 60%, 67%);
  --blue-300: hsl(215, 65%, 77%);
  --blue-200: hsl(215, 70%, 86%);    /* focus-visible, changed-state text */
  --blue-100: hsl(215, 75%, 93%);    /* tinted alert background (light tint) */

  /* ===== STATUS — green ===== */
  --green-700: hsl(145, 55%, 25%);   /* success bg in dark mode */
  --green-500: hsl(145, 52%, 42%);   /* was --accent: #36d17d */
  --green-100: hsl(145, 55%, 92%);   /* success text in dark mode (near-white green) */

  /* ===== STATUS — amber ===== */
  --amber-700: hsl(38, 80%, 30%);    /* warning bg in dark mode */
  --amber-500: hsl(38, 85%, 50%);    /* was --warn: #ffc857 */
  --amber-100: hsl(38, 90%, 93%);    /* warning text in dark mode */

  /* ===== STATUS — red ===== */
  --red-900:   hsl(5, 65%, 12%);     /* danger button background (dark) */
  --red-700:   hsl(5, 65%, 30%);     /* error bg in dark mode */
  --red-500:   hsl(5, 68%, 48%);     /* was --danger: #ff6b7a (slightly toned) */
  --red-100:   hsl(5, 70%, 94%);     /* error text in dark mode (near-white red) */

  /* ===== STATUS — purple (advisory / read-only evidence) ===== */
  --purple-700: hsl(265, 45%, 30%);
  --purple-500: hsl(265, 48%, 52%);
  --purple-100: hsl(265, 52%, 94%);

  /* ===== TYPE SCALE ===== */
  --text-xs:   11px;   /* metadata, footnotes, table cells, chips */
  --text-sm:   13px;   /* secondary labels, form labels, table headers */
  --text-base: 15px;   /* default body text */
  --text-md:   17px;   /* panel headings, section titles */
  --text-lg:   20px;   /* page-level section headings, topbar h1 */
  --text-xl:   24px;   /* brand name */
  --text-2xl:  30px;   /* single-stat callouts (metric values) */

  /* ===== SPACING SCALE =====
     Use these for all new margin/padding/gap values.
     Existing rules will be migrated incrementally (Stage 3).
     Zero and auto are the only raw values permitted for spacing.        */
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

  /* ===== SHADOWS — dark-mode adapted (higher opacity than light-mode spec) ===== */
  --shadow-1: 0 1px 2px hsl(220 15% 0% / 0.30);
  --shadow-2: 0 2px 4px hsl(220 15% 0% / 0.35);
  --shadow-3: 0 4px 8px hsl(220 15% 0% / 0.40), 0 1px 3px hsl(220 15% 0% / 0.25);
  --shadow-4: 0 8px 24px hsl(220 15% 0% / 0.45), 0 2px 6px hsl(220 15% 0% / 0.30);
  --shadow-5: 0 16px 48px hsl(220 15% 0% / 0.50), 0 4px 12px hsl(220 15% 0% / 0.35);

  /* ===== LEGACY ALIASES =====
     These keep existing CSS working during the color migration.
     Each alias is removed once all references to the old name are gone (Task 7).   */
  --bg:        var(--grey-900);
  --surface:   var(--grey-800);
  --surface-2: var(--grey-700);
  --line:      var(--grey-600);
  --text:      var(--grey-100);
  --muted:     var(--grey-300);
  --accent:    var(--green-500);
  --accent-2:  var(--blue-500);
  --warn:      var(--amber-500);
  --danger:    var(--red-500);
}
```

**Verify after applying:**

```powershell
$css = "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css"

# New tokens must be present
Select-String -Path $css -Pattern '--grey-900'     # must match
Select-String -Path $css -Pattern '--blue-500'     # must match
Select-String -Path $css -Pattern '--green-500'    # must match
Select-String -Path $css -Pattern '--red-900'      # must match
Select-String -Path $css -Pattern '--text-xs'      # must match
Select-String -Path $css -Pattern '--space-1'      # must match
Select-String -Path $css -Pattern '--shadow-1'     # must match

# Legacy aliases must still be present (not yet removed)
Select-String -Path $css -Pattern '--bg:'          # must match alias line
Select-String -Path $css -Pattern '--muted:'       # must match alias line
```

After applying, open the UI in a WebView or browser. It must render with correct layout — not blank, not unstyled. The colors may shift slightly compared to the old values; that is expected.

---

## Task 4 — Migrate raw hex colors to tokens

Go through every CSS rule in `styles.css`. For each raw hex value, replace it with the appropriate new token using the mapping table below. Then replace every `var(--old-name)` with `var(--new-name)` where the old name was a raw alias.

### Hex-to-token mapping

| Raw hex | Replace with | Rule context |
|---|---|---|
| `#0e151d` | `var(--grey-900)` | Body background, canvas |
| `#0f1923` | `var(--grey-800)` | Sidebar background, input background |
| `#121d27` | `var(--grey-800)` | Surface (--surface old value) |
| `#172635` | `var(--grey-700)` | Surface-2 |
| `#132131` | `var(--grey-800)` | Table `th` background (sticky header) |
| `#163525` | `var(--blue-900)` | Nav active background — **was green; now blue per design ref** |
| `#1a2938` | `var(--grey-700)` | Chip idle background (close-readiness, refresh-health) |
| `#253342` | `var(--grey-700)` | State-pill idle background |
| `#1d3550` | `var(--blue-800)` | State "updating" background |
| `#133459` | `var(--blue-900)` | State "processing" / "audit" background |
| `#26394a` | `var(--grey-600)` | Canvas border |
| `#2a4054` | `var(--grey-600)` | Line / border (--line old value) |
| `#123823` | `var(--green-700)` | Success / ok / completed / safe background |
| `#1f7f4a` | `var(--green-500)` | Success border |
| `#3f3311` | `var(--amber-700)` | Warning background |
| `#a3742b` | `var(--amber-500)` | Warning border |
| `#4a1d27` | `var(--red-700)` | Error / failed / blocked / danger background |
| `#5b2a36` | `var(--red-700)` | Danger button border |
| `#2a141b` | `var(--red-900)` | Danger button background (deepest dark red) |
| `#d3e1ec` | `var(--grey-100)` | Text-block / pre element text color |
| `#a8f0c4` | `var(--green-100)` | Success state text (bright green on dark) |
| `#ffc1c9` | `var(--red-100)` | Error state text (bright red on dark) |
| `#ffe29a` | `var(--amber-100)` | Warning state text (bright amber on dark) |
| `#b9d7ff` | `var(--blue-200)` | Changed state text |
| `#bfdbfe` | `var(--blue-200)` | Updating state text |
| `#ffd88a` | `var(--amber-100)` | Warning chip text (refresh-health warning) |

### rgba() migration

Five `rgba()` blends exist in the file. Replace each using one of two strategies:

**Strategy A — `color-mix()` (preferred if WebView2 build is Chromium 119+):**

```css
/* was: border-bottom: 1px solid rgba(42, 64, 84, 0.72) */
border-bottom: 1px solid color-mix(in srgb, var(--grey-600) 72%, transparent);

/* was: background: rgba(54, 209, 125, 0.16)  — selected row */
background: color-mix(in srgb, var(--green-500) 16%, transparent);

/* was: background: rgba(101, 167, 255, 0.08)  — hover row */
background: color-mix(in srgb, var(--blue-500) 8%, transparent);

/* was: background: rgba(101, 167, 255, 0.14)  — focus-visible row */
background: color-mix(in srgb, var(--blue-500) 14%, transparent);

/* was: box-shadow: inset 0 1px 0 rgba(101, 167, 255, 0.65), inset 0 -1px 0 rgba(101, 167, 255, 0.65) */
box-shadow: inset 0 1px 0 color-mix(in srgb, var(--blue-500) 65%, transparent),
            inset 0 -1px 0 color-mix(in srgb, var(--blue-500) 65%, transparent);
```

**Strategy B — discrete alpha tokens (fallback if color-mix() is unavailable):**

Add these to `:root` and use them instead:

```css
/* Add to :root if color-mix() is not available */
--green-500-alpha-16: hsl(145, 52%, 42%, 0.16);
--blue-500-alpha-08:  hsl(215, 55%, 56%, 0.08);
--blue-500-alpha-14:  hsl(215, 55%, 56%, 0.14);
--blue-500-alpha-65:  hsl(215, 55%, 56%, 0.65);
--grey-600-alpha-72:  hsl(220, 10%, 26%, 0.72);
```

> **Decision required:** Determine which WebView2 version is in use. If `color-mix()` is supported, use Strategy A. If not, use Strategy B and append the alpha tokens to `:root`. Document which strategy was chosen as a comment on the first `color-mix()` or alpha-token line.

### After completing all hex and rgba replacements, verify:

```powershell
$css = "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css"

# Raw hex outside comments — must be 0
$hexRemaining = (Select-String -Path $css -Pattern '#[0-9a-fA-F]{6}\b' |
  Where-Object { $_.Line -notmatch '^\s*/\*' -and $_.Line -notmatch '//.*#' }).Count
Write-Host "Remaining raw hex values: $hexRemaining"   # target: 0

# rgba() outside comments — must be 0
$rgbaRemaining = (Select-String -Path $css -Pattern 'rgba\s*\(' |
  Where-Object { $_.Line -notmatch '^\s*/\*' }).Count
Write-Host "Remaining rgba() calls: $rgbaRemaining"    # target: 0

# Spot-check new tokens are in use
Select-String -Path $css -Pattern 'var\(--grey-600\)'   # should appear multiple times
Select-String -Path $css -Pattern 'var\(--green-700\)'  # should appear (success states)
Select-String -Path $css -Pattern 'var\(--red-900\)'    # should appear (danger button)
```

---

## Task 5 — Migrate font sizes to type scale tokens

Find every `font-size:` declaration in `styles.css` that uses a raw pixel value. Replace with the appropriate type scale token from the mapping below.

### Font size mapping

| Raw value | Replace with | Notes |
|---|---|---|
| `12px` | `var(--text-xs)` | Most frequent — table cells, chips, `.note`, form labels, textarea |
| `13px` | `var(--text-sm)` | Brand version, panel subheadings, filter field, settings summary headings |
| `16px` | `var(--text-md)` | Panel headings `h2` / `h3` — 17px is acceptable rounding |
| `18px` | `var(--text-lg)` | Topbar `h1` — see note in audit |
| `22px` | `var(--text-xl)` | `.brand-name` — 24px is a minimal size increase |
| `26px` | `var(--text-2xl)` | `.metric strong` single-stat callouts — see audit note |

**Also fix non-standard font-weight:**

`.topbar h1` uses `font-weight: 650` — not a web-standard CSS weight value. Replace with `font-weight: 600`.

**Verify:**

```powershell
$css = "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css"

# All font-size declarations must use a token. Zero results means pass.
Select-String -Path $css -Pattern 'font-size\s*:' |
  Where-Object { $_.Line -notmatch 'var\(--text-' -and $_.Line -notmatch 'font-size:\s*inherit' }
# Must return 0.

# Non-standard font-weight 650 must be gone
Select-String -Path $css -Pattern 'font-weight:\s*650'
# Must return 0.
```

---

## Task 6 — Apply personality rules (Section 1 and Section 7)

The design reference defines specific structural decisions that differ from the current implementation. Apply each in order.

### 6a — Border radius on containers and controls

**Rule (Section 1):** Panels, cards, and containers use `border-radius: 0` or at most `2px`. Reserve rounded shapes only for chips and badges.

Find every `border-radius: 8px` in the file and change it per the table:

| Selector(s) | Current | Change to |
|---|---|---|
| `.metric`, `.panel` | `8px` | `2px` |
| `.topbar` | `8px` | `2px` |
| `.nav-button`, `.secondary-button`, `.danger-button` | `8px` | `2px` |
| `.option-panel` | `8px` | `2px` |
| `.table-wrap`, `.command-table-wrap`, `.detail-table-wrap` | `8px` (inherited from .table-wrap rule) | `2px` |
| `input`, `select`, `textarea` | `8px` | `2px` |
| `canvas` | `8px` | `2px` |
| `.state-pill`, `.close-readiness`, `.refresh-health` | `999px` | **Keep** — these are status chips/pills |

### 6b — Nav active state: green → blue

**Rule (Section 6):** The active navigation item uses an accent border on the left edge (`3–4px`, `--blue-500`) and a slightly tinted background. Inactive items have no background.

Replace the `.nav-button.is-active` rule:

```css
/* Before */
.nav-button.is-active {
  background: #163525;
  border-color: var(--accent);
}

/* After */
.nav-button.is-active {
  background: var(--blue-900);
  border-color: var(--blue-500);
  border-left-width: 3px;
}
```

### 6c — Nav hover and button hover: green → blue

Replace the hover rule for nav/secondary/danger buttons:

```css
/* Before */
.nav-button:hover,
.secondary-button:hover,
.danger-button:hover {
  border-color: var(--accent);
}

/* After */
.nav-button:hover,
.secondary-button:hover {
  border-color: var(--blue-500);
}

.danger-button:hover {
  border-color: var(--red-500);
}
```

### 6d — Add primary button class (Section 7)

The design reference defines a `.primary-button` tier. Inspect `index.html` to determine whether any existing button uses inline styling or an unlisted class to serve as the primary action button. Then add this class to `styles.css` immediately after the `.danger-button` hover rule:

```css
.primary-button {
  border: none;
  background: var(--blue-500);
  color: var(--grey-50);
  border-radius: 2px;
  padding: var(--space-4) var(--space-7);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
}

.primary-button:hover {
  background: var(--blue-600);
}

.primary-button:active {
  background: var(--blue-700);
  box-shadow: none;
}

.primary-button:disabled {
  background: var(--grey-600);
  color: var(--grey-400);
  cursor: not-allowed;
}
```

> **Note:** Do not apply `.primary-button` to any existing button in `index.html` in this stage. Adding the class definition now means Stage 3 can wire it up without touching CSS. Only define the class; do not touch HTML button elements.

### 6e — Table header styling (Section 6)

Update the `th` rule to match the design reference column header spec:

```css
/* Before */
th {
  position: sticky;
  top: 0;
  background: #132131;
  color: var(--muted);
  z-index: 1;
}

/* After (other properties remain) */
th {
  position: sticky;
  top: 0;
  background: var(--grey-800);   /* was raw hex */
  color: var(--grey-300);        /* was var(--muted) — now explicit token */
  font-size: var(--text-xs);     /* was 12px */
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  z-index: 1;
}
```

### 6f — Selected row: green → blue (Section 6)

The design reference uses `--blue-100` background + left `--blue-500` border for selected rows, not a translucent green.

```css
/* Before */
tr.is-selected td {
  background: rgba(54, 209, 125, 0.16);
}

/* After */
tr.is-selected td {
  background: var(--blue-800);
}

tr.is-selected td:first-child {
  border-left: 3px solid var(--blue-500);
}
```

**Verify Task 6:**

```powershell
$css = "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css"

# border-radius: 8px should only remain on chips
$eightPx = Select-String -Path $css -Pattern 'border-radius:\s*8px'
foreach ($m in $eightPx) { Write-Host $m.Line }
# Review: only .state-pill / .close-readiness / .refresh-health lines are acceptable.
# Any panel, button, input, canvas, or table-wrap line is a fail.

# Nav active should reference blue tokens
Select-String -Path $css -Pattern 'nav-button\.is-active' -A 5
# Must contain --blue-900 or --blue-500 reference. Must NOT contain --accent or a raw green hex.

# Table th must have uppercase and letter-spacing
Select-String -Path $css -Pattern 'letter-spacing: 0.04em'   # must return at least 1 result
Select-String -Path $css -Pattern 'text-transform: uppercase' # must return at least 1 result

# Primary button class defined
Select-String -Path $css -Pattern '\.primary-button'          # must return results
```

---

## Task 7 — Remove legacy aliases from :root

After Tasks 4, 5, and 6, the old token names (`--bg`, `--surface`, `--surface-2`, `--line`, `--text`, `--muted`, `--accent`, `--accent-2`, `--warn`, `--danger`) should no longer appear in any CSS rule — only in the alias block itself.

**Verify all old references are gone before removing aliases:**

```powershell
$css = "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css"

$oldTokens = @(
  'var\(--bg\)', 'var\(--surface\)', 'var\(--surface-2\)',
  'var\(--line\)', 'var\(--text\)', 'var\(--muted\)',
  'var\(--accent\)', 'var\(--accent-2\)', 'var\(--warn\)', 'var\(--danger\)'
)

$found = $false
foreach ($t in $oldTokens) {
  # Exclude alias definition lines (lines that contain the token name after a colon in :root)
  $refs = Select-String -Path $css -Pattern $t |
    Where-Object { $_.Line -notmatch '^\s+--' }
  if ($refs) {
    Write-Host "Still in use outside alias block: $t ($($refs.Count) refs)"
    $refs | ForEach-Object { Write-Host "  Line $($_.LineNumber): $($_.Line.Trim())" }
    $found = $true
  }
}
if (-not $found) { Write-Host "All old token references are gone. Safe to remove aliases." }
# Must print "All old token references are gone." before proceeding.
```

Once verified, remove the entire `/* ===== LEGACY ALIASES ===== */` block from `:root`.

**Final verification:**

```powershell
$css = "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css"

# Token system — all design reference tokens present in :root
@('--grey-900', '--blue-500', '--green-500', '--amber-500', '--red-500',
  '--purple-500', '--text-xs', '--space-1', '--shadow-1') | ForEach-Object {
  $n = (Select-String -Path $css -Pattern [regex]::Escape($_)).Count
  if ($n -eq 0) { Write-Host "MISSING: $_" }
}
# Must print nothing.

# Old ad-hoc token definitions gone from :root
@('--bg:', '--surface:', '--surface-2:', '--line:', '--muted:',
  '--accent:', '--accent-2:', '--warn:', '--danger:') | ForEach-Object {
  if (Select-String -Path $css -Pattern [regex]::Escape($_)) {
    Write-Host "STILL DEFINED: $_"
  }
}
# Must print nothing.

# Raw hex values gone
$hex = (Select-String -Path $css -Pattern '#[0-9a-fA-F]{6}\b' |
  Where-Object { $_.Line -notmatch '^\s*/\*' }).Count
Write-Host "Remaining raw hex: $hex"   # must be 0
```

---

## Task 8 — Resolve uncertain panel classifications

Codex may have flagged panels with `<!-- REVIEW: panel type uncertain -->` comments. This task resolves every one.

### For each uncertain panel:

1. Find the panel in `index.html`. Note its surrounding `data-page-panel` value (which page it belongs to).
2. Read the panel's heading to identify its canonical name.
3. Look up that page in Section 8 of `V5_UI_DESIGN_REFERENCE.md`. Find the canonical panel name.
4. If the Section 8 Notes column says "(read-only)" → classify as `evidence`.
5. If Section 8 does not specify, inspect the panel's children:
   - Contains `<input>`, `<select>`, or `<textarea>` → `interactive`
   - Contains a `<button>` that is NOT labeled "Copy" or "Copy checklist" → `interactive`
   - Contains only `<pre>`, `<table>`, `<p>`, `<strong>`, readout spans, or a Copy button → `evidence`
6. Replace the placeholder attribute and remove the `<!-- REVIEW -->` comment.

**Example — resolving an uncertain panel:**

```html
<!-- Before (Codex left this) -->
<section class="panel" data-panel-type="evidence"<!-- REVIEW: panel type uncertain -->">

<!-- After (Claude resolves it) -->
<section class="panel" data-panel-type="evidence">
```

**Verify:**

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# All REVIEW comments resolved
$remaining = (Select-String -Path $html -Pattern 'REVIEW: panel type uncertain').Count
Write-Host "Unresolved uncertain panels: $remaining"   # must be 0

# Recount final panel classification
$ev = (Select-String -Path $html -Pattern 'data-panel-type="evidence"').Count
$in = (Select-String -Path $html -Pattern 'data-panel-type="interactive"').Count
Write-Host "Final count — evidence: $ev  interactive: $in  uncertain: 0"
```

---

## Task 9 — Inventory and log discipline

### 9a — Verify no new DOM IDs were introduced

Stage 1 and Stage 2 are text-and-attribute changes only. No new `id=` attributes should have been added.

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"
$currentCount = (Select-String -Path $html -Pattern '\bid="').Count
Write-Host "Current DOM id count: $currentCount"
# Compare to the count recorded in Docs\WEBVIEW_DOM_ID_INVENTORY.md.
# If counts match: WEBVIEW_DOM_ID_INVENTORY.md is n/a for this stage.
# If counts differ: update the inventory file to add or remove the changed IDs.
```

### 9b — Verify no new global exports were introduced

```powershell
$jsDir = "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets"
$currentExports = (Select-String -Path "$jsDir\*.js" -Pattern 'window\.').Count
Write-Host "Current window.* export references: $currentExports"
# Compare to WEBVIEW_GLOBAL_EXPORT_INVENTORY.md.
# If no new exports: mark as n/a.
```

### 9c — Append to DOC_TOUCH_LOG.md

Append one row to `Docs/DOC_TOUCH_LOG.md`. Fill in the actual counts from Task 7 verification and Task 8:

```
| 2026-05-15 | V5 UI Stage 2 — CSS token system, personality rules, panel classification | `REMEDIATION_CHANGELOG.md` | `WEBVIEW_DOM_ID_INVENTORY.md` (no new ids), `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` (no new exports), `API_ROUTE_INVENTORY.md` (no new routes), `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` (no mutation changes), `TAURI_WEBVIEW_PARITY_MATRIX.md` (no parity change), `VALIDATION_LADDER_RUNBOOK.md` (no rung changes), `DOCS_INDEX.md` (no new docs) | CSS: [N] raw hex values replaced, [N] font-size values tokenized; personality rules applied (border-radius 8px→2px, nav active green→blue, th uppercase+tracking); primary-button class defined; [N] uncertain panels resolved |
```

Replace `[N]` with the actual counts from verification outputs before appending.

### 9d — Append to REMEDIATION_CHANGELOG.md

Add a dated H2 entry following the established format in that file. Minimum content:

```markdown
## 2026-05-15 — V5 UI Implementation Stage 2: CSS token system and personality rules

**What changed:**
- `styles.css`: `:root` replaced with design reference token system (grey scale 9 shades,
  blue scale 9 shades, status colors 3 shades each, 7-step type scale, 14-step spacing scale,
  5 shadow levels)
- `styles.css`: [N] raw hex values replaced with token vars
- `styles.css`: [N] font-size declarations tokenized
- `styles.css`: `border-radius: 8px` reduced to `2px` on all containers (chips kept at 999px)
- `styles.css`: nav active state changed from green to blue (`--blue-900` bg, `--blue-500` border)
- `styles.css`: table `th` now has uppercase, `letter-spacing: 0.04em`, `font-weight: 600`
- `styles.css`: selected row changed from translucent green to `--blue-800` bg + left accent
- `styles.css`: `.primary-button` class defined (not yet applied to HTML)
- `index.html`: [N] uncertain panel type comments resolved

**Verification passed:**
- 0 raw hex values remaining
- 0 raw font-size values remaining
- 0 `<!-- REVIEW -->` comments remaining
- 0 panels missing `data-panel-type`

**What was deliberately NOT changed in Stage 2:**
- Spacing values in `styles.css` — raw px spacing remains; will be tokenized in Stage 3
- Button elements in `index.html` — `.primary-button` class defined but not applied yet
- No DOM IDs, exports, or API routes added
```

---

## Completion checklist

Before handing this work off, confirm every item below:

- [ ] Task 1: Stage 1 gate passed — all nav, heading, button, and panel-type checks returned expected results
- [ ] Task 2: CSS audit reviewed — findings match current file; color scheme decision recorded (dark mode retained)
- [ ] Task 3: `:root` token block applied — new tokens present, legacy aliases in place, UI renders without breaking
- [ ] Task 4: All raw hex and all rgba() values replaced — 0 remaining raw hex, 0 remaining rgba() calls
- [ ] Task 5: All font-size values use type scale tokens — 0 remaining raw px font-size rules; non-standard `font-weight: 650` fixed
- [ ] Task 6: Personality rules applied — border-radius 2px on containers; nav active uses `--blue-500`; th has uppercase and letter-spacing; selected row uses blue tokens
- [ ] Task 7: Legacy aliases removed from `:root` — all old token names (`--bg`, `--muted`, etc.) gone from both `:root` definition and all CSS rules
- [ ] Task 8: All `<!-- REVIEW: panel type uncertain -->` comments resolved — 0 uncertain panels remain
- [ ] Task 9: DOM ID count checked; export count checked; DOC_TOUCH_LOG row appended; REMEDIATION_CHANGELOG entry added
- [ ] No spacing values in `styles.css` were changed (spacing migration is Stage 3)
- [ ] No button elements in `index.html` had their `class` attribute changed
- [ ] No `data-page`, `id`, or `data-panel-type` attributes in `index.html` were changed

---

## What Stage 3 will cover (out of scope here)

For completeness, items that are deliberately deferred:

- **Spacing migration:** Replace all raw `margin`/`padding`/`gap` values in `styles.css` with `--space-*` tokens. This requires touching almost every rule and is a dedicated pass.
- **Primary button application:** Wire the `.primary-button` class to the "Start Pipeline", "Save Settings", and "Submit Rename to Backend" buttons in `index.html`.
- **Evidence panel tint:** Apply `background: var(--purple-700)` tint to panels classified as `evidence` where the design reference calls it out (Lifecycle Handoff on Workers page, State Summary on Diagnostics).
- **Empty state design:** Add proper empty states (icon + headline + explanation) to tables that can have zero rows.
- **Light mode option:** If operator sign-off is obtained, redefine the `:root` token values for a light-mode variant. Class names and markup require no changes.
