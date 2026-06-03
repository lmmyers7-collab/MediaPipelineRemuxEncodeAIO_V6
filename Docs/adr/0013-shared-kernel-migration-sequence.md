# 0013. Shared-kernel migration sequence

Status: proposed
Date: 2026-06-02

## Context

ADR-0012 decided to extract a neutral shared kernel for the cross-layer
types and constants and named the unresolved mechanics — package name,
`config_keys`/`subprocess_runner` placement, sequencing, and shim strategy
— as open questions. This ADR resolves those mechanics and defines the move
order. It does not re-litigate ADR-0012's direction.

The order is dictated by the actual import structure among the kernel
candidates, read from `V6_dependency_atlas_assets/dependency_module_edges.csv`.
Two facts shape the sequence:

Internal dependencies (a module must move no earlier than what it imports):

- `models -> models_core`, `models -> models_media_paths`. The three move
  as one unit; `models_core` and `models_media_paths` are leaves.
- `dto_commands`, `dto_inventory`, `dto_workspaces` each import `dto_base`.
- `dto` imports `dto_base`, `dto_commands`, `dto_inventory`,
  `dto_workspaces` **and** `application.dto_status` (outside the candidate
  set — see complications).
- `contracts` (the aggregator) imports `contracts.base` **and** eight
  sibling contract modules: `active_job`, `completed_job`, `control_flag`,
  `pending_publish`, `pipeline_events`, `process_result`, `progress`,
  `queue_snapshot`.

Leaves with no outbound deps (safe to move first): `models`, `models_core`,
`models_media_paths`, `dto_base`, `dto_commands`, `dto_inventory`,
`dto_workspaces`, `contracts.base`, `config_keys`, `subprocess_runner`.

Two complications the atlas surfaced:

1. **`dto` is not a clean leaf.** It pulls `application.dto_status`, which is
   not in ADR-0012's candidate list. Moving `dto` either drags `dto_status`
   into the kernel or leaves `dto` behind.
2. **`contracts` is an aggregator over a subpackage.** Moving the
   `contracts` name means moving the whole `contracts/` package (base plus
   eight job/event contracts), not a single module.

## Decision

Resolve ADR-0012's open questions as follows, then migrate in five waves,
one PR per numbered step, each within `CLAUDE.md §3` size limits.

Resolved mechanics:

- **Package**: a new package `app/kernel/`. AGENTS.md §2 requires new code
  to live under `app/`, and `app/` is already a recognized domain, so this
  needs no AGENTS.md edit. It is neutral in the dependency sense: it imports
  nothing else from `app.*` or `mediapipeline_desktop_app.*`; both layers may
  import it. (A top-level `kernel/` was considered but rejected — it would
  require amending AGENTS.md §2's structure, a standing-policy change outside
  per-session authority.)
- **Shim strategy**: each move leaves a re-export shim at the old path
  (`from kernel.X import *  # moved by ADR-0013`) so importers keep working
  between waves. A final cleanup PR rewrites importers and deletes the
  shims. This avoids a 120-file atomic rewrite.
- **`config_keys`**: move the whole module to `kernel/config_keys.py`. Do
  not split individual keys — the desktop-only keys riding along are
  constants with no behaviour, and splitting raises churn for no boundary
  benefit.
- **`subprocess_runner`**: move to `app/kernel/runtime/subprocess_runner.py`. It
  is the one non-type member; it is process-execution machinery, but it is a
  dependency-free leaf consumed across the layer boundary (17 importers), so
  it belongs in the neutral package. Keep it in a `runtime/` submodule to
  signal it is utility, not contract.

Migration waves (each step = one PR: move the module, leave a re-export
shim at the old path, re-run validation; importer rewrites are deferred to
the Wave 6 cleanup so each step stays small):

- **Wave 1 — models unit (largest win, fully self-contained).**
  1. Move `models`, `models_core`, `models_media_paths` to
     `app/kernel/` (flat modules; `models.py` keeps its relative imports of
     the other two). Shims at the old paths repoint 92 / 5 / 1 importers.
     Note: `models.py`
     defines `QueueRecord` (queue types touch AGENTS.md §7); the move is
     type-only but the PR takes the queue/settings validation rung, not
     self-certification.
- **Wave 2 — standalone leaf constants/utilities.**
  2. Move `config_keys` (25 importers).
  3. Move `subprocess_runner` -> `app/kernel/runtime/` (17 importers).
- **Wave 3 — DTO base then dependents.**
  4. Move `dto_base` (13 importers) first.
  5. Move `dto_commands` (33), `dto_inventory` (10), `dto_workspaces` (6)
     — each imports only `dto_base`, now in the kernel.
- **Wave 4 — DTO aggregator.**
  6. `dto_status` was verified to import only `dataclasses` and `dto_base`
     (a pure DTO, no app/desktop behaviour), so move `dto_status` into
     `app/kernel/`, then move `dto` (which depends on it plus the Wave 3
     members).
- **Wave 5 — contracts subpackage.**
  7. Move `contracts.base` (9 importers) — a clean leaf.
  8. Move the remaining `contracts/` modules (`active_job`, `completed_job`,
     `control_flag`, `pending_publish`, `pipeline_events`, `process_result`,
     `progress`, `queue_snapshot`) and the `contracts` aggregator as one
     unit, since the aggregator re-exports all of them.
- **Wave 6 — cleanup.**
  9. Rewrite any remaining importers to the `kernel/` paths and delete all
     shims. Run the dependency-direction check from ADR-0012 §Validation and
     require it green.

`pending_publish` (Wave 5, step 8) touches release-critical state per
`CLAUDE.md §9`; that step requires the validation rung named in
`AGENTS.md §5` and explicit operator approval before it runs. It is a
mechanical move, but it is in a high-risk area, so it does not self-certify.

## Consequences

Code and structure:

- New `app/kernel/` package; ~120 `app/*` files and a smaller set of
  `desktop/*` files have import paths rewritten over six PRs. Shims keep the
  tree importable between waves.
- After Wave 1, `models` is no longer a 92-importer godfile under the
  desktop package.
- After Wave 6, the `app.* -> mediapipeline_desktop_app.*` type edges are
  gone and ADR-0012's invariant is enforceable.

Operational surface:

- None at runtime. Same types, same JSON contracts (ADR-0004), same logs.
  The `pending_publish` move must prove byte-identical manifest behaviour.

Testing and CI:

- Full Python suite per wave. Add the ADR-0012 dependency-direction check in
  Wave 6 so the inversion cannot return.

Migration cost:

- Six to nine PRs. Risk is import churn and the two complications, not
  logic. Shims bound the blast radius of any single PR.

Reversibility:

- Per wave, high (revert the PR, restore the shim). After Wave 6 deletes the
  shims, reversal means reintroducing the inversion — expensive.

## Alternatives considered

**Atomic single-PR rewrite.** Move everything and rewrite all ~120
importers at once. Smallest total churn, but a single huge PR that violates
`CLAUDE.md §3` size limits and is near-impossible to review or bisect.
Rejected.

**No shims; rewrite importers in each move PR.** Cleaner history, but each
wave then touches every importer of the moved module in one PR — Wave 1
alone would be 90+ files. Shims trade a little temporary indirection for
reviewable, bisectable steps. Chosen.

**Move `dto` and `contracts` first because they are the named aggregators.**
They are the *most* entangled (the two complications), not the least. Moving
them first would force the `dto_status` and eight-contract decisions up
front and stall the easy, high-value `models` win. Sequenced last instead.

**Keep `subprocess_runner` out of the kernel as a separate shared util
package.** Defensible — it is not a type. But it is a dependency-free leaf
crossing the same boundary; a `kernel/runtime/` submodule gets the boundary
benefit without inventing a second neutral package. Revisit only if the
kernel accumulates more non-type utilities.

## Validation

This ADR is enforced when:

- Each wave PR lands with the full Python suite green
  (`DesktopApp\Runtime\Python\python.exe -m pytest`).
- Wave 6 adds and passes the dependency-direction check named in
  ADR-0012 §Validation (no `app.* -> mediapipeline_desktop_app.*` type
  edges; `app/kernel/` imports nothing else from `app.*` or
  `mediapipeline_desktop_app.*`).
- The `pending_publish` move (step 8) passes the high-risk validation rung
  in `AGENTS.md §5` with operator sign-off.

Until those checks exist and pass, this ADR is a proposal only.

## Supersedes / superseded by

None. Implements ADR-0012 (shared-kernel extraction); does not supersede it.
