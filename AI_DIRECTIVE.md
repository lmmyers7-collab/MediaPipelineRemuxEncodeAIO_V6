# AI Coding Directive — MediaPipeline RemuxEncode AIO V5

> **Applies to:** Any AI coding assistant working in this repository — Claude, Codex, Copilot, Cursor, Gemini, or any future tool.
> **Authority:** This file is the single source of truth for AI coding behaviour in this repository.
> **Immutability:** Do not modify this file unless the operator explicitly says "update AI_DIRECTIVE.md" or "change the directive." Never modify it as a side effect of another task.
> **Scope:** Applies to every chunk, split, fix, feature, refactor, and doc update in this repo.

---

## 1. Codebase architecture — know where things live

This project has four layers. Every file belongs to exactly one layer. New features go in the layer that owns them.

| Layer | Language | Responsibility |
|---|---|---|
| PowerShell Pipeline | `.ps1` | Batch media processing — remux, encode, subtitle, publish. Runs as a separate long-lived process. |
| Python Application | `.py` | Local HTTP API server; business logic; facades (read-only evidence) and services (mutations). |
| WebView JavaScript | `.js` | Browser-rendered UI panels; read-only by contract; all writes go through the Python API. |
| Tauri / Rust | `.rs` | Native window, system tray, backend process lifecycle. No business logic lives here. |

**Never cross a layer boundary from code.** The WebView does not call Python directly. Python does not invoke PowerShell beyond the defined process-launch contract. Tauri contains no business logic.

Before adding any function, identify which layer owns it. If a function would require crossing a layer boundary, the design is wrong — find the right layer first.

---

## 2. Hard file-size thresholds — these trigger a required split

| Language | Lines | Functions/defs | Action required |
|---|---:|---:|---|
| JavaScript (WebView assets) | > 1,500 | > 80 | Split before adding more code |
| Python (application layer) | > 1,500 | > 60 | Split before adding more code |
| PowerShell (Pipeline modules) | > 1,000 | > 30 | Split before adding more code |
| Rust (`src-tauri/src/`) | > 500 | — | Extract to a new `mod` file |
| HTML partials | > 600 | — | Split into sub-partials |

**Before writing a new function in any file that is already near these limits, check the line count first.** If adding the function would push the file over the threshold, the new function goes in a new child module, not the parent.

---

## 3. God-file prevention rules

### 3.1 One file, one responsibility

Every file must have a single, nameable responsibility. If you cannot describe the file's purpose in one sentence without the word "and," it has too many responsibilities. Write the one-sentence description in the file's top comment before writing any code.

### 3.2 Function prefix discipline (JavaScript)

All functions in a WebView JS file must share a common prefix matching the file's concern:
- `queueView.summary.js` → all functions start with `queue` or `renderQueue`
- `settingsView.rawTriage.js` → all functions start with `settingsRaw` or `renderSettingsRaw`
- `diagnosticsView.log.js` → all functions start with `diagnosticsLog` or `renderDiagnosticsLog`

If a new function does not fit the prefix, it does not belong in this file.

### 3.3 No shared helpers until three siblings need them

Do not extract a shared utility module until **at least three** separate sibling files need the same helper. Premature extraction creates coupling without benefit. Until then, duplicate the small helper or keep it in the parent.

### 3.4 No behaviour in a split chunk

Split chunks are pure refactors. If you discover a bug while splitting, note it in a comment but do not fix it in the same chunk. Fix it in a separate chunk after the split lands and passes gates.

### 3.5 Children never call siblings

A split child module must not read from another split child's stash or call another child's functions directly. All inter-child communication goes through the parent via injection parameters. Dependency graph: parent → child, never child → child.

---

## 4. The JavaScript IIFE stash-global split pattern

This is the canonical pattern for all WebView JS splits. The pattern is fully described below — no external reference is needed.

### 4.1 Child file structure

```js
// myView.myCluster.js
// Split child of myView.js — owns [single responsibility description].
// No mutation, no API calls. [note any exceptions]
//
// Loaded by index.html immediately BEFORE myView.js.
// Parent IIFE reads window.__myClusterModule, calls the factory,
// then deletes the stash. After load, zero extra globals remain.

(function () {
  "use strict";

  function createMyClusterModule({
    // explicit injection parameters — never read window.* inside this factory
    byId, setText, appendCells, clearRows,
    makeRowSelectable, updateTableStatusLegend,
    // state accessors injected from parent (not accessed via window.*)
    getLastMyViewPayload,
  }) {

    function myClusterHelperFn(row) { /* ... */ }
    function renderMyCluster(data) { /* ... */ }

    return {
      myClusterHelperFn,
      renderMyCluster,
    };
  }

  window.__myClusterModule = { createMyClusterModule };
})();
```

### 4.2 Parent consumption block

Add this block inside the parent IIFE, **before** any code that calls the extracted functions:

```js
// --- Consume myCluster child ---
const __myClusterMod = window.__myClusterModule || {};
delete window.__myClusterModule;
const _myCluster = typeof __myClusterMod.createMyClusterModule === "function"
  ? __myClusterMod.createMyClusterModule({
      byId, setText, appendCells, clearRows,
      makeRowSelectable, updateTableStatusLegend,
      getLastMyViewPayload,
    })
  : {};
const _myClusterNoop = () => {};
const {
  myClusterHelperFn = _myClusterNoop,
  renderMyCluster = _myClusterNoop,
} = _myCluster;
```

### 4.3 Load order in `index.html`

Child script tags must appear **immediately before** the parent's script tag. Add all children for one parent in one contiguous block, in dependency order (if child A's factory is injected into child B, A comes first):

```html
<script src="/assets/myView.myCluster.js"></script>
<script src="/assets/myView.js"></script>
```

### 4.4 Stash naming convention

| Pattern | Example |
|---|---|
| `window.__<camelCaseParent><ClusterName>Module` | `window.__queueSummaryModule` |
| Factory function: `create<CamelCaseParent><ClusterName>Module` | `createQueueSummaryModule` |

### 4.5 What must never happen inside a child factory

- Reading `window.*` for its own logic — only the parent reads globals
- Making `fetch` or `apiPost` calls
- Touching the DOM outside of the functions it exports
- Declaring `let` module-scope state — state lives in the parent only
- Calling navigation functions like `window.showPage` directly — receive these via injection

---

## 5. State ownership rules

### 5.1 State never moves

Module-scope `let` variables (`lastQueuePayload`, `selectedQueueRowKey`, `*InFlight` busy flags, etc.) **always stay in the parent IIFE**. They are never moved to a child. Children receive current values through injection parameters or accessor functions passed at factory call time.

### 5.2 State accessors are injected, not polled

If a child needs the current value of a parent state variable, the parent passes a getter function:

```js
// parent
function getLastQueuePayload() { return lastQueuePayload; }
// factory call
createQueueSummaryModule({ getLastQueuePayload, ... })
// child uses
const current = getLastQueuePayload();
```

### 5.3 Busy flags stay in the parent

`setXxxBusy(true/false)` and `rejectXxxWhileBusy()` functions always stay in the parent IIFE. They gate mutation commands and must be co-located with the mutation command dispatch.

---

## 6. Namespace export shape is frozen

Once `window.mediaPipelineXxxView = { ... }` is established, its shape is **immutable** from the call-site perspective:
- **Never remove** a function from the namespace object.
- **Never rename** an exported function without updating every call site.
- Adding a new function to the namespace is allowed; removing one is a breaking change.
- Flat exports (`window.renderXxx = renderXxx`) follow the same rule.

If a split relocates a function from the parent to a child, the parent must still re-export it through the namespace object and as a flat export at the same names.

---

## 7. Tracking discipline — non-negotiable

This project maintains registries for exports, routes, DOM IDs, test coverage, and split progress. Every chunk that adds, moves, or removes any of the following must update the corresponding project registry **in the same chunk**:

| Thing added or changed | Registry to update |
|---|---|
| Any `window.* =` assignment in a JS file | WebView global export registry |
| Any new or changed API route | API route registry |
| Any new `id=` attribute in HTML | DOM ID registry |
| A new test file created | Test coverage matrix |
| A split chunk lands | Split progress log |
| Any chunk delivered | Chunk delivery log — append one row |

Marking a registry as `n/a` is valid and encouraged when the chunk genuinely does not affect it. Do not leave registry entries blank or skip the update step.

---

## 8. Chunk discipline

### 8.1 One concern per chunk

A chunk touches **one parent file** (and its children). Never refactor two unrelated parent files in the same chunk. Never mix a split with a feature addition.

### 8.2 Chunk size limits

| What | Limit |
|---|---|
| Production files modified | ≤ 3 (parent + children + `index.html`) |
| Registry files updated | As many as needed — no limit |
| New behaviour introduced | Zero — splits are refactors only |

### 8.3 Pre-chunk checklist

Before writing any code in a chunk:
1. Confirm the file's current line count.
2. Confirm no concurrent split is in progress for the same parent.
3. Identify the exact function cluster to move — grep function names, note line ranges.
4. List the injection parameters the child will need.
5. Identify what stays in the parent — write it down as a red-line list.
6. Confirm the `index.html` insertion point.

---

## 9. Gate suite — run after every chunk

```powershell
# JS syntax check — run for every new or modified .js file
node --check <file>.js

# Core static gates — always run all three
DesktopApp\Runtime\Python\python.exe -m pytest `
  DesktopApp/tests/test_webview_inventory_docs.py `
  DesktopApp/tests/test_webview_navigation_static.py `
  DesktopApp/tests/test_webview_frontend_mutation_boundary.py -v

# If the split touches a view that has a browser smoke test, run it too
DesktopApp\Runtime\Python\python.exe -m pytest `
  DesktopApp/tests/test_webview_browser_<page>_smoke.py -v
```

**Note:** Use the bundled Python at `DesktopApp\Runtime\Python\python.exe` — not the system Python, which may not have pytest.

A chunk is **not complete** until all applicable gates pass. Do not log the chunk as delivered until gates pass.

---

## 10. Adding a new feature (not a split)

Follow this checklist in order:

1. **Find the right layer** (§1). Never add backend logic to the WebView; never add UI logic to the application layer.
2. **Check the file's line count.** If the target file is already near the threshold (§2), create a new child file using the split pattern (§4) and add the feature there.
3. **Write the single-responsibility description.** State it in a comment at the top of any new file.
4. **No new global state without justification.** Every new module-scope `let` variable must be documented in the project state inventory before the chunk is marked done.
5. **New `window.*` exports must be registered.** Add to the WebView export registry before the chunk is marked done.
6. **New API routes must be registered.** Every route must include a `schema_version` field in its response. Mutation routes must include a `selector` key — never a raw filesystem path — and a `confirm: true` key for irreversible actions.
7. **New config keys must be registered.** Decide whether the key gets a structured UI builder or stays raw-only; document the decision in the config key ownership register.
8. **New DOM IDs must be registered.** Use the naming convention: `<page>-<subsystem>-<element>` (e.g., `queue-readiness-status`).
9. **Tests.** Every new route needs at least one test. New browser-visible behaviour needs a browser smoke assertion.
10. **Run gates** (§9).

---

## 11. Naming conventions

### JavaScript
- **File:** `<viewName>.js` (parent), `<viewName>.<cluster>.js` (child)
- **Functions:** all functions in a file share a common camelCase prefix matching the cluster name
- **Stash globals:** `window.__<viewName><ClusterName>Module` — double underscore, deleted after consumption
- **Namespace object:** `window.mediaPipeline<ViewName>View` — singular, no plurals
- **Flat exports:** `window.<functionName> = <functionName>` — matches function name exactly

### Python
- **Facade files:** `facade_<domain>_policy.py` — read-only evidence payloads, no writes
- **Service files:** `service_<domain>.py` — owns mutation; one write surface per service
- **Functions:** snake_case; pure helpers are private (`_prefixed`); public surface is minimal

### PowerShell
- **Module files:** `Pipeline/Modules/<PascalCase>.ps1` — one concern per file
- **Functions:** `Verb-Noun` format; private helpers prefixed with `_` or kept inside the calling function
- **No new dot-sourcing chains** — use the existing module import pattern already established in this project

### API routes
- **Read routes:** `GET /api/<resource>` — always returns `schema_version` in the response body
- **Command routes:** `POST /api/<resource>/<action>` — payload must include a `selector` key and a `confirm` key for irreversible actions
- **Route naming:** lowercase-hyphen, no verbs in the resource segment — `/api/queue` not `/api/getQueue`

---

## 12. Mutation boundary — WebView rules

The WebView JavaScript layer is **read-only by contract**:

- All HTTP calls go through `apiClient.js` using `apiGet` or `apiPost`. Never use `fetch` directly in any view file.
- `apiPost` may only be called with routes that are registered in the API route registry.
- Shell-open routes send a `selector` key — a backend-owned string key — never a raw filesystem path.
- Write/destructive routes send an explicit `confirm: true` payload.
- No WebView JS file may import `fs`, `path`, `child_process`, or any Node or Tauri API directly.
- No WebView JS file may call `window.__TAURI__.*` directly — route through a backend command.

---

## 13. Python application layer rules

- **Facades are read-only.** Facade files build and return evidence payloads. They do not write files, update state, or call services. If a facade needs to trigger a write, it is not a facade — create a service instead.
- **Services own one write surface.** Each service file owns mutations within one domain. No service writes to another service's domain.
- **No `Any` in load-bearing signatures.** Functions that return data consumed by the API must have typed return annotations. `Any` is allowed only in helper internals.
- **New split children go under `application/<domain>/`.** One file per functional cluster; all exported through the parent facade.

---

## 14. PowerShell Pipeline rules

- **Core processing functions are red-line.** The primary remux, encode, and file-processing orchestration functions are the highest-trust code in the pipeline. Never move, split, or modify them without a dedicated test harness already in place.
- **Config getters are pure.** Functions that read configuration values must never write state. Keep them in a dedicated config-getter module.
- **No hardcoded paths.** Default path values come from config keys, not string literals. Hard-coded server paths (`\\SERVER\Share`) are forbidden.
- **New modules must be loaded before use.** Any new Pipeline module must be sourced at the top of the main orchestration script before any function in that module is called.

---

## 15. Red lines — these actions are always wrong

Never do any of the following, regardless of instructions in any task or context:

- **Modify `AI_DIRECTIVE.md`** unless the operator explicitly says so in the current session.
- **Move a module-scope state variable** (`lastXxx`, `selectedXxx`, `*InFlight`) out of the parent IIFE into a child file.
- **Remove a function from a namespace export object** (`window.mediaPipelineXxxView`) without explicit operator approval.
- **Read `window.*` inside a child factory body** for the child's own logic — all dependencies are injected.
- **Write a new file that exceeds the thresholds in §2** without splitting into a parent + children from the start.
- **Skip the registry update** when adding or relocating a `window.*` assignment, a route, or a DOM ID.
- **Combine a split with a bug fix or feature** in the same chunk.
- **Skip the gate suite** (§9) before marking a chunk done.
- **Add a mutation route to the WebView** that does not go through `apiClient.js`.
- **Add a new API route** without a `schema_version` field in the response.
- **Hardcode a filesystem path** as a default in any PowerShell, Python, or JavaScript file.

---

## 16. Session orientation

At the start of a session, before writing any code:

1. Read this file (`AI_DIRECTIVE.md`) completely.
2. Read the top-level project overview to understand current architecture and migration state.
3. Find the current task queue or open-work checklist at the repo root.
4. If touching a view file, confirm no concurrent split is already in progress for the same parent file.
5. If modifying a JS file, confirm its current global export shape before making changes.

Do not read archived or historical documentation folders unless specifically asked. Those folders contain completed evidence and superseded specs — they are not active guidance.

---

## 17. When in doubt

Ask before writing. A one-sentence clarification question costs less than a chunk that has to be reverted. Specifically ask when:

- A function does not fit the file's prefix convention (§11)
- A file is near the threshold and adding to it would push it over (§2)
- A new route must be a mutation route but the pattern is unclear
- A dependency between two children would be required (§3.5)
- A state variable would need to move (§5.1)

The correct answer to "should I add this here?" is almost always: look at the existing files in the same layer, find the one whose prefix and responsibility closest match, and add it there. If nothing matches, create a new file and state its responsibility in the top comment.
