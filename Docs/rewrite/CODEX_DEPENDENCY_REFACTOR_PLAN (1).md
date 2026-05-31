# Codex dependency cleanup plan for MediaPipelineRemuxEncodeAIO V6

Use this as an external Codex task prompt. If it is later promoted into the
repository, place it under `Docs/architecture/` and update `CHANGELOG.md` when
implementation starts. Do not create a root `PLANS.md`, `*_REPORT.md`,
`*_FIXES.md`, or `*_CHECKLIST.md` file for this work.

## Goal

Clean up the Python dependency architecture without changing product behavior,
media policy, queue behavior, publish/drain behavior, settings persistence, or
the WebView/Tauri operator boundary.

The current V6 repository already has a domain-oriented structure. The cleanup
must fit that layout:

| Area | Current role |
|---|---|
| `app/<domain>/` | Canonical Python domain services, contracts, facades, storage, validation, and orchestration. New Python domain code should land here. |
| `DesktopApp/mediapipeline_desktop_app/` | Local API host, compatibility package, backend-served WebView integration. Do not move reusable domain behavior here unless it is desktop-host specific. |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/` | Vanilla-JS WebView SPA assets. Frontend code must not own media policy or filesystem mutation. |
| `DesktopApp/tauri_shell/` | Tauri/WebView2 shell. Shell lifecycle stays separate from Python domain refactors. |
| `engine/<domain>/` | Active PowerShell implementation. Do not create new dotted `Pipeline/Modules/*.ps1` files. |
| `Pipeline/` | Engine entry scripts, config/profiles, schemas, bundled tools, setup/audit helpers, and PowerShell tests. `Pipeline/Modules` is retired. |
| `tests/` | New behavior/domain Python tests, especially `tests/contract/`, `tests/tooling/`, and domain folders. |
| `DesktopApp/tests/` | Existing Local API/WebView/backend compatibility tests. Keep using these when touched behavior still lives behind the desktop host. |
| `SmokeTests/` | PowerShell smoke wrappers. New smoke wrappers go here, not at the repo root. |
| `scripts/dev/` | Developer guardrails and generated-artifact tooling. New dependency checks should live here. |
| `Docs/generated/` | Generated navigation and dependency outputs. Do not hand-edit. |

The current graph has a good property: no module-level cycles were reported in
the supplied dependency SVG. However, the graph still shows several
architectural risks that need to be verified against the actual V6 source:

- package-level cycles are present;
- `app.shared`, `app.shared.utils`, and `app.shared.constants` are overloaded dependency hubs;
- `app.config` imports higher-level runtime behavior;
- `app.observability`, `app.status`, and `app.telemetry` have ownership-boundary pressure;
- `app.api` imports `app.ui.preferences`;
- package `__init__.py` files may hide coupling through re-export/barrel imports.

The generated `Docs/generated/DEPENDENCY_GRAPH.md` edge convention is
dependency domain -> consuming domain. For example, `config --> api` means API
code imports config code. Codex must verify any supplied SVG or CSV uses the
same convention before acting on it.

---

## V6 operating rules for Codex

1. Start every implementation session by reading `AGENTS.md`,
   `Docs/CURRENT_PROJECT_STATE.md`, `OPEN_WORK_CHECKLIST.md`, and
   `Docs/generated/PROJECT_INDEX.md`.
2. Before opening full source files, check the matching `summaries/<path>.md`.
   Open full source only when the summary is high priority or the task needs
   details the summary does not list.
3. Use the bundled interpreter for Python validation:

   ```powershell
   .\DesktopApp\Runtime\Python\python.exe
   ```

4. Do not do this as one giant refactor. Work one phase at a time and stop
   after each phase with a summary, checks run, and remaining risks.
5. Do not change behavior intentionally. This is architecture cleanup, not a
   feature change.
6. Do not add third-party dependencies unless the project already uses the tool.
   Prefer stdlib `ast` for dependency checks.
7. Do not hide cycles by moving imports into functions unless the import is
   genuinely optional/lazy.
8. Do not replace `shared` with another vague dumping ground such as `common`,
   `helpers`, or `misc`.
9. Avoid broad formatting changes. Keep diffs reviewable.
10. Prefer moving types/contracts downward into `app.contracts` instead of
    making low-level packages import high-level services.
11. Before deleting or moving a public import path, search the repo and tests
    for all call sites.
12. Avoid compatibility shims that preserve the forbidden package cycle. If an
    external compatibility concern is real, document it and ask before
    preserving the cycle.
13. Record new architectural rules under `Docs/architecture/` and enforce them
    with `scripts/dev/` tooling plus focused tests.
14. After repo source edits, run `scripts/dev/refresh_summaries.py` for touched
    files or ensure the pre-commit hook will regenerate summaries.

---

## Existing dependency tooling to reuse

Do not start Phase 0 by inventing unrelated paths. V6 already has dependency
and summary tooling:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_dependency_atlas.py
```

Current outputs:

- `Docs/generated/PROJECT_INDEX.md`: generated source index from summaries.
- `Docs/generated/DEPENDENCY_GRAPH.md`: generated cross-domain dependency graph.
- `V6_dependency_atlas.html`
- `V6_dependency_atlas.png`
- `V6_dependency_atlas.svg`
- `V6_dependency_atlas_assets/dependency_summary.csv`
- `V6_dependency_atlas_assets/dependency_edges.csv`
- `V6_dependency_atlas_assets/dependency_module_edges.csv`

Phase 0 should extend or add `scripts/dev/check_dependency_boundaries.py` only
if the existing generators do not already provide the needed machine-checkable
signals. If a new checker is needed, add focused tests under `tests/tooling/`.

---

## Current graph facts to verify

Treat these as seed facts from the supplied graph and current repo inspection,
not as final truth. Regenerate the atlas and read the CSVs before changing
imports.

### Highest-risk hubs

These modules are used by many other modules and should be treated as high-risk
change points:

| Module | Why it is risky |
|---|---|
| `app.shared` | Broad package-level hub; direct package imports hide ownership. |
| `app.shared.constants` | Mixes constants across domains and imports desktop contracts. |
| `app.shared.utils` | Shared IO/path/tail helpers used across unrelated domains. |
| `app.shared.protocols` | Service protocol types may belong in domain packages or `app.contracts`. |
| `app.contracts` | Correct place for stable cross-domain DTOs, but still high fan-in. |
| `app.api.command_results` | Shared command response boundary; changing it affects Local API routes. |
| `app.config.*` | Low-level config should not depend on runtime planning. |
| `app.status.*`, `app.observability.*`, `app.telemetry.*` | Status/metric ownership needs one direction. |

### Current cross-boundary imports already visible

Verify these from the source/atlas before editing:

```text
app.config.settings_patch_facade imports app.orchestration.planner
app.config.preset_migration imports app.decide.processing_decision
app.observability.status_facade imports app.status.*
app.observability.status_policy imports app.telemetry.gpu_usage
app.api.commands_ui_preferences imports app.ui.preferences
```

Also inventory imports from:

```text
app.shared
app.shared.constants
app.shared.utils
app.shared.protocols
```

---

## Target architecture rules

### Rule A: no package-level cycles

The dependency graph must be acyclic at both levels:

```text
module-level graph:  no cycles
package-level graph: no cycles
```

A package-level cycle is still a design problem even when module-level imports
are acyclic.

### Rule B: `app.config` stays low-level

`app.config` may import:

```text
app.contracts
app.shared, only as a temporary exception while shared is being split
stdlib / already-approved third-party config libraries
```

`app.config` must not import:

```text
app.orchestration
app.decide
app.api
app.ui
app.queue
app.processes
app.rename
app.status
app.telemetry
```

Potential actions:

- Move `app.config.settings_patch_facade` to a higher-level owner if it builds
  pipeline plans. Candidate: `app.orchestration.settings_patch_facade`.
- If `app.config.preset_migration` needs decision types, move pure
  type/enum/dataclass contracts to `app.contracts` and make both config and
  decide import that contract.
- Keep config migrations pure: transform, validate, and emit config data. They
  should not plan runtime orchestration.

### Rule C: orchestration may consume config, config may not consume orchestration

Desired direction:

```text
app.orchestration -> app.config
```

Forbidden direction:

```text
app.config -> app.orchestration
```

Here `A -> B` means "A imports B."

### Rule D: status, observability, and telemetry need one direction

Adopt this direction unless source review proves a better one:

```text
app.status -> app.observability -> app.telemetry
```

Interpretation:

- `app.telemetry` gathers raw GPU/system/runtime facts.
- `app.observability` reads/writes observability files, snapshots, metrics, and
  runtime evidence.
- `app.status` builds user-facing status views from observability, telemetry
  evidence, and active job state.

Likely actions:

- Move `app.observability.status_facade` into `app.status` if it builds
  status-facing responses.
- Keep `app.observability.status_files` in observability if it only owns file
  reads/writes.
- Keep raw GPU/system collection in `app.telemetry`.
- Do not let telemetry depend on observability storage concerns.
- Do not let observability depend on status presentation concerns.

### Rule E: API must not import UI implementation

Forbidden:

```text
app.api -> app.ui
```

Likely action:

- Move neutral preference schema/path/read/write logic out of
  `app.ui.preferences` to a neutral owner such as:

  ```text
  app.contracts.preferences
  app.ui_preferences
  app.user_preferences
  ```

- Let `app.api.commands_ui_preferences` and `app.ui.preferences` both import
  the neutral module.
- Keep actual UI rendering labels/layout/defaults inside `app.ui`.

### Rule F: reduce direct imports from `app.shared`

Current V6 still uses these surfaces:

```text
app.shared
app.shared.utils
app.shared.constants
app.shared.protocols
```

New rule:

```python
# Forbidden once baseline is clean
from app.shared import X
import app.shared

# Temporary warning until split
from app.shared.utils import X
from app.shared.constants import X
from app.shared.protocols import X
```

Prefer ownership-specific modules:

```text
app.paths.*
app.storage.*
app.processes.*
app.contracts.*
app.<domain>.<specific_owner>
```

Move helpers into the domain that owns the behavior when they are not truly
cross-cutting.

### Rule G: package `__init__.py` files should not hide coupling

For most packages, `__init__.py` should be empty or contain only minimal
package metadata.

Avoid broad re-export barrels like:

```python
from .service import *
from .types import SomeType
from .utils import helper
```

Exceptions must be deliberate, documented, and stable.

---

## Implementation phases

### Phase 0 — Baseline and dependency guard

Do this first. It should be nearly behavior-free.

Tasks:

1. Confirm current generated files are fresh:

   ```powershell
   .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check
   .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check
   ```

2. Regenerate or inspect the richer dependency atlas:

   ```powershell
   .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_dependency_atlas.py
   ```

3. Inspect these outputs:

   ```text
   Docs/generated/DEPENDENCY_GRAPH.md
   V6_dependency_atlas_assets/dependency_summary.csv
   V6_dependency_atlas_assets/dependency_edges.csv
   V6_dependency_atlas_assets/dependency_module_edges.csv
   ```

4. Decide whether to extend `scripts/dev/generate_dependency_atlas.py` or add a
   separate `scripts/dev/check_dependency_boundaries.py`. Prefer a separate
   checker if failing rules and report generation would make the atlas tool too
   complicated.
5. The checker should report:
   - internal imports among `app.*` modules;
   - module-level cycles;
   - package-level cycles;
   - direct imports from `app.shared`;
   - direct imports from `app.shared.utils`;
   - direct imports from `app.shared.constants`;
   - direct imports from `app.shared.protocols`;
   - forbidden imports from `app.config` to higher-level packages;
   - forbidden imports from `app.api` to `app.ui`;
   - forbidden imports that violate the chosen status/observability/telemetry direction.
6. Add focused coverage under `tests/tooling/`, for example:

   ```text
   tests/tooling/test_dependency_boundaries.py
   ```

7. Start in report-only or baseline-allowlist mode if the repo currently
   violates the rules. Do not break the build on known violations until a phase
   clears them.
8. Document the rule and command under:

   ```text
   Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md
   ```

Acceptance criteria:

- Existing targeted tests still pass.
- The checker reproduces the package cycles or explains why the actual code
  differs from the supplied graph.
- The checker can run locally without network access and without new packages.
- Generated docs remain current.
- The new docs do not point to retired root launchers or `Pipeline/Modules`.

Stop after this phase and report findings.

### Phase 1 — Break `app.config` -> higher-level imports

Target outcome:

```text
app.orchestration may import app.config
app.config must not import app.orchestration
app.config should not import app.decide
```

Tasks:

1. Inspect summaries first:

   ```text
   summaries/app/config/settings_patch_facade.py.md
   summaries/app/config/preset_migration.py.md
   summaries/app/orchestration/planner.py.md
   summaries/app/decide/processing_decision.py.md
   ```

2. Inspect full source only as needed.
3. If `app.config.settings_patch_facade` calls orchestration/planning logic,
   move it to:

   ```text
   app/orchestration/settings_patch_facade.py
   ```

   or another existing higher-level owner if source review shows a better fit.

4. Update internal imports to the new location.
5. Do not leave a compatibility shim in `app.config` that imports
   `app.orchestration`.
6. If `app.config.preset_migration` imports decision-only types from
   `app.decide.processing_decision`, move pure contracts to `app.contracts`.
7. If `preset_migration` imports real decision behavior, move that behavior out
   of config and into orchestration/planning.

Acceptance criteria:

- `app.config` has no imports from `app.orchestration`.
- Preferably, `app.config` also has no imports from `app.decide`.
- The `app.config` / `app.orchestration` package cycle is gone.
- Relevant config/orchestration tests pass.
- Public behavior is unchanged.

Suggested validation:

```powershell
.\DesktopApp\Runtime\Python\python.exe -m pytest tests\contract tests\orchestration DesktopApp\tests\test_settings_pipeline_plan_preview.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py
```

Stop after this phase and report exact moved modules/imports.

### Phase 2 — Break `app.observability` / `app.status` / `app.telemetry` cycles

Target direction:

```text
app.status -> app.observability -> app.telemetry
```

Tasks:

1. Inspect summaries first:

   ```text
   summaries/app/observability/status_facade.py.md
   summaries/app/observability/status_policy.py.md
   summaries/app/observability/status_files.py.md
   summaries/app/status/service.py.md
   summaries/app/telemetry/service.py.md
   summaries/app/telemetry/gpu_usage.py.md
   ```

2. Move `app.observability.status_facade` into `app.status` if it constructs
   status-facing responses.
3. Update imports so `app.observability` no longer imports:

   ```text
   app.status
   app.status.active_jobs
   app.status.eta
   app.status.ffmpeg_progress
   ```

4. Keep observability storage/read/write code in `app.observability`.
5. Keep raw GPU/system collection code in `app.telemetry`.
6. Keep user-facing aggregation in `app.status`.
7. Do not move WebView telemetry JavaScript; this phase is Python-domain only.

Acceptance criteria:

- `app.observability` does not import `app.status`.
- `app.telemetry` does not import `app.observability`.
- The package cycle among `app.observability`, `app.status`, and
  `app.telemetry` is gone.
- Status/telemetry tests pass.
- Status output remains unchanged unless tests intentionally expose a bug.

Suggested validation:

```powershell
.\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_status_service.py DesktopApp\tests\test_telemetry_service.py DesktopApp\tests\test_facade_status_policy.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py
```

Stop after this phase and report naming choices.

### Phase 3 — Fix API/UI boundary

Target outcome:

```text
app.api must not import app.ui
```

Tasks:

1. Inspect summaries first:

   ```text
   summaries/app/api/commands_ui_preferences.py.md
   summaries/app/ui/preferences.py.md
   ```

2. Separate neutral preference model/schema/path/read/write logic from
   UI-specific behavior.
3. Move neutral logic to one of:

   ```text
   app/contracts/preferences.py
   app/ui_preferences.py
   app/user_preferences.py
   ```

   Choose the name that best matches the source after inspection. Prefer
   `app/contracts/preferences.py` if it is mostly stable DTO/schema, and prefer
   a small domain module if it owns file IO.

4. Update `app.api.commands_ui_preferences` to import the neutral module.
5. Keep only UI-specific behavior in `app.ui.preferences`.

Acceptance criteria:

- `app.api.commands_ui_preferences` no longer imports `app.ui` or
  `app.ui.preferences`.
- API tests pass.
- UI preference behavior is unchanged.
- Dependency checker reports no API-to-UI imports.

Suggested validation:

```powershell
.\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_application_facade_local_api.py DesktopApp\tests\test_application_facade_web_static.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py
```

Stop after this phase and report what moved.

### Phase 4 — Reduce `app.shared` blast radius

Target outcome:

```text
No direct imports from app.shared.
Reduced imports from app.shared.utils/constants/protocols.
Clearer ownership of helper code.
```

Tasks:

1. Inventory all imports from:

   ```text
   app.shared
   app.shared.utils
   app.shared.constants
   app.shared.protocols
   ```

2. Categorize each imported symbol:

   ```text
   pure generic helper
   path/file helper
   time/date helper
   serialization helper
   process/subprocess helper
   domain-specific helper
   constant owned by one domain
   protocol/type that belongs in contracts or an owning domain
   ```

3. Move only obvious low-risk items in the first pass.
4. Prefer existing V6 domains over new generic packages:

   ```text
   app.paths
   app.storage
   app.processes
   app.contracts
   app.rename
   app.publish
   app.queue
   app.status
   app.<owning-domain>
   ```

5. Do not create `app.common`, `app.helpers`, or another dumping ground.
6. Keep the first pass mechanical. Do not rewrite logic.
7. Split this phase into sub-phases if a symbol touches media movement,
   pending publish, rename apply, settings save, command journal, or process
   lifecycle behavior.

Acceptance criteria:

- Direct consumers of `app.shared` drop substantially, ideally to zero.
- `app/shared/__init__.py` is empty or nearly empty.
- No new package cycles are introduced.
- Existing targeted tests pass.
- Dependency checker reports the new fan-in counts.

Stop after each sub-phase and report remaining `shared` hotspots.

### Phase 5 — Harden dependency rules

Target outcome:

Architecture rules are enforced automatically.

Tasks:

1. Turn the dependency checker from report-only into fail-on-new-violation
   mode.
2. Use a baseline allowlist only for violations that cannot be safely fixed yet.
3. Put the allowlist in a durable architecture location, for example:

   ```text
   Docs/architecture/dependency_boundary_allowlist.txt
   ```

4. Every allowlist entry must include:

   ```text
   importing module
   imported module
   rule id
   reason
   target removal phase or owner
   ```

5. Add the checker to existing local safety nets where appropriate:

   ```powershell
   .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling
   .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py
   .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py
   ```

Acceptance criteria:

- New package cycles fail the check.
- New `app.api -> app.ui` imports fail the check.
- New `app.config -> app.orchestration` imports fail the check.
- New direct `app.shared` imports fail the check unless temporarily allowlisted.
- Documentation explains how to run and update the checker.
- `Docs/generated/PROJECT_INDEX.md` and `Docs/generated/DEPENDENCY_GRAPH.md`
  remain generated and current.

---

## Suggested checker rules

Hard failures once the baseline is clean:

```text
NO_PACKAGE_CYCLES
NO_MODULE_CYCLES
NO_CONFIG_TO_ORCHESTRATION
NO_CONFIG_TO_DECIDE
NO_API_TO_UI
NO_OBSERVABILITY_TO_STATUS
NO_TELEMETRY_TO_OBSERVABILITY
NO_DIRECT_APP_SHARED_IMPORTS
```

Warnings until explicitly cleaned:

```text
NO_SHARED_UTILS_IMPORTS
NO_SHARED_CONSTANTS_IMPORTS
NO_SHARED_PROTOCOLS_IMPORTS
NO_BARREL_INIT_REEXPORTS
NO_DOMAIN_IMPORTS_FROM_SHARED_CONSTANTS
```

---

## Suggested Codex first prompt

Paste this to Codex together with this plan:

```text
Follow CODEX_DEPENDENCY_REFACTOR_PLAN.md. Start with Phase 0 only.

Read AGENTS.md, Docs/CURRENT_PROJECT_STATE.md, OPEN_WORK_CHECKLIST.md, and
Docs/generated/PROJECT_INDEX.md first. Use the bundled Python at
DesktopApp\Runtime\Python\python.exe.

Before changing behavior, inspect the existing dependency tooling:
scripts/dev/generate_project_index.py, scripts/dev/generate_dependency_atlas.py,
Docs/generated/DEPENDENCY_GRAPH.md, and V6_dependency_atlas_assets/*.csv.

Create or update the smallest stdlib-only dependency boundary checker under
scripts/dev/ and add focused tests under tests/tooling. Do not fix architecture
yet. Make the checker reproducible, document it under Docs/architecture/, run
the checks/tests you can infer from the repo, then stop and summarize the exact
violations found in the actual code.
```

After Phase 0 is reviewed, continue with:

```text
Proceed with Phase 1 only: break the app.config -> app.orchestration package
cycle and reduce app.config -> app.decide if the imported items are really
contracts. Keep behavior unchanged, avoid compatibility shims that preserve the
cycle, run the dependency checker and targeted tests, refresh summaries for
touched files, then stop with a concise summary.
```

---

## Review checklist for each phase

Before accepting a patch, verify:

```text
[ ] The patch addresses only the requested phase.
[ ] Public behavior is unchanged.
[ ] No broad formatting-only churn was introduced.
[ ] Existing tests pass or failures are explained.
[ ] Dependency checker output improved.
[ ] No new package-level cycles were introduced.
[ ] No new `app.shared` imports were introduced.
[ ] No import was merely hidden inside a function to silence the graph.
[ ] Moved modules have clear ownership and names.
[ ] New Python domain code lives under `app/<domain>/` unless there is a clear host-specific reason.
[ ] New tooling lives under `scripts/dev/`.
[ ] New docs live under `Docs/architecture/` or another existing topic folder, not the repo root.
[ ] Generated docs are regenerated or checked when touched inputs changed.
[ ] Summaries are refreshed for touched source files.
```

---

## Things not to do

Do not solve this by doing any of the following:

```text
Moving everything into app.shared
Creating app.common as a new dumping ground
Adding function-local imports just to hide cycles
Leaving compatibility shims that preserve forbidden package cycles
Renaming many modules without reducing coupling
Changing APIs and architecture in the same patch
Making the dependency checker depend on network access
Ignoring package-level cycles because module-level cycles are clean
Creating new flat facade_*.py or service_*.py files
Creating new dotted Pipeline/Modules/*.ps1 files
Reintroducing removed root launcher paths
Hand-editing Docs/generated/PROJECT_INDEX.md or Docs/generated/DEPENDENCY_GRAPH.md
```

---

## Definition of done for the full cleanup

The cleanup is complete when:

```text
[ ] module-level cycles are still zero
[ ] package-level cycles are zero
[ ] app.config does not import app.orchestration or app.decide
[ ] app.api does not import app.ui
[ ] app.observability/status/telemetry follow one documented direction
[ ] direct app.shared imports are zero or explicitly justified
[ ] app.shared.utils/constants/protocols have been split or reduced to small, defensible surfaces
[ ] package __init__.py files do not hide major dependencies
[ ] dependency rules are documented under Docs/architecture/
[ ] dependency rules are enforced by a repeatable scripts/dev command
[ ] generated dependency/index artifacts remain current
[ ] summaries are current
[ ] tests pass
```
