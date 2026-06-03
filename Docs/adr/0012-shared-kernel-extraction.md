# 0012. Extract a shared kernel for cross-layer types

Status: proposed
Date: 2026-06-02

## Context

The V6 dependency atlas (`V6_dependency_atlas_assets/dependency_module_edges.csv`,
829 module edges across 364 modules) shows a structural inversion between
the two top-level layers established by ADR-0001 (folder-by-domain) and
carved out by ADR-0011 (V5 -> V6 split):

- `app/*` (domain/business logic) imports `mediapipeline_desktop_app/*`
  (the desktop host package) on **208 edges from 119 distinct app files**.
- The reverse, `desktop -> app`, is only **66 edges from 10 files** — the
  facade/services composition root wiring app logic into the host, which
  is the expected direction.

The `app -> desktop` traffic is not spread evenly; it is concentrated on a
small set of host modules that are really shared *types and constants*, not
desktop behaviour:

| Host module imported by `app/*`            | app importers | total importers |
| ------------------------------------------ | ------------: | --------------: |
| `mediapipeline_desktop_app.models`         |            78 |              92 |
| `...application.dto_commands`              |            32 |              33 |
| `...subprocess_runner`                      |            17 |              17 |
| `...config_keys`                            |            14 |              25 |
| `...application.dto_inventory`             |             9 |              10 |
| `...application.dto_base`                   |             8 |              13 |
| `...application.dto`                        |             7 |               8 |
| `...contracts` (base)                       |             6 |               9 |
| `...application.dto_workspaces`            |             5 |               6 |
| `...models_core`                            |             4 |               5 |

`mediapipeline_desktop_app.models` alone has **92 importers** — roughly a
quarter of all modules depend on it. It is the single largest coupling
point in the codebase (next highest fan-in is 33). This is the "godfile"
class the guardrails (`scripts/dev/ai_guardrail.py`) already watch for.

Two problems follow:

1. **Layer inversion.** Business logic cannot be reasoned about, tested, or
   eventually lifted out of the desktop package while its core data models,
   DTOs, and constants physically live under `mediapipeline_desktop_app`.
   This is the structural blocker for the monolith-split campaign (ADR-0010).
2. **Blast radius.** A change to `models` or `dto_commands` ripples across
   most of the tree, so the modules that change most are also the ones most
   depended upon — the worst stability/abstractness position.

Doing nothing means every future `app/*` module adds another `app -> desktop`
edge, deepening the inversion the split was meant to remove.

## Decision

Extract a neutral **shared kernel** package that holds the cross-layer
types and constants, and have both `app/*` and `mediapipeline_desktop_app/*`
depend on it. The kernel depends on **neither** layer.

In force once this ADR is accepted and the migration ADR(s) land:

- A new top-level package (working name `app/kernel/`, final name an open
  question below) is the single home for:
  - the pydantic contract/model types currently in
    `mediapipeline_desktop_app.models` and `...models_core`
  - the DTO family `dto`, `dto_base`, `dto_commands`, `dto_inventory`,
    `dto_workspaces` currently under `...application`
  - the shared contract base currently in `...contracts`
- The kernel imports only third-party libraries (pydantic per ADR-0004) and
  the Python stdlib. It must not import `app.*` or
  `mediapipeline_desktop_app.*`.
- `app/*` and `mediapipeline_desktop_app/*` import shared types **from the
  kernel only**. No new `app -> desktop` type imports are added.
- The target invariant: **zero `app.* -> mediapipeline_desktop_app.*`
  edges** in `dependency_module_edges.csv` once migration completes
  (excluding the composition root's intentional `desktop -> app` wiring).

This ADR decides the *direction and shape* only. The mechanical move is a
separate, sequenced migration (see Open questions) so each step stays under
the change-size and review limits in `CLAUDE.md §3`.

## Open questions

To be resolved in the migration ADR, not here:

- **Package name and location.** `app/kernel/`, a sibling top-level
  `kernel/`, or a distributable `mediapipeline_core` package. ADR-0001's
  folder-by-domain convention favours a clearly-named top-level domain.
- **`config_keys` placement.** It is half desktop-config, half shared
  constants (25 importers, 14 from `app`). Decide whether the whole module
  moves or only the keys consumed across the layer boundary.
- **`subprocess_runner` placement.** 17 importers; it is process-execution
  machinery, arguably its own shared utility rather than a "type." It may
  belong in the kernel or in a separate shared-utility module.
- **Migration sequencing.** Proposed order, smallest blast radius last:
  `models_core` -> `contracts` base -> `dto_base` -> remaining `dto_*` ->
  `models`. Each step is one PR with the guardrail re-run.
- **Re-export shims vs. hard cutover.** Whether to leave temporary
  `from app.kernel import *` shims at the old paths during migration or
  rewrite all imports atomically per module.

## Consequences

Code and structure:

- One new package; ~120 `app/*` files have import paths rewritten over the
  migration. No behaviour change — these are move-and-reimport edits.
- `mediapipeline_desktop_app.models` stops being a god module; its 92
  importers repoint at the kernel, and the desktop package shrinks to host
  behaviour plus composition.
- Reinforces ADR-0001 (domain boundaries) and unblocks ADR-0010 (split
  campaign) by giving `app/` a dependency-free foundation.

Operational surface:

- None at runtime. Same types, same JSON contracts (ADR-0004), same logs.
  Pure import-graph refactor.

Testing and CI:

- The dependency-direction check below becomes enforceable and should be
  added to the guardrail so the inversion cannot silently return.

Migration cost:

- Moderate and spread across several PRs. The risk is import churn, not
  logic; mitigated by sequencing and by re-running the full Python suite
  per step.

Reversibility:

- High. The kernel can be folded back into the desktop package by reversing
  the moves, though that would reintroduce the inversion. The decision is
  cheap to revisit before migration starts, expensive after the import
  rewrites land.

## Alternatives considered

**Leave types under `mediapipeline_desktop_app` and accept the inversion.**
Zero migration cost, but it permanently couples business logic to the
desktop host and blocks ADR-0010. The atlas shows the inversion deepening
with every new `app` module; deferring only raises the eventual cost.

**Move the types into `app/` instead of a new kernel.** Flips the arrow —
now `desktop -> app` for core types — but `app/` still becomes a de-facto
shared kernel without saying so, and the desktop package's own use of the
types (14 of the 92 `models` importers are desktop) would invert in the
other direction. A neutral kernel that neither layer owns is cleaner.

**Split `models` into per-domain model modules in place.** Reduces the
single godfile's fan-in but leaves every model still under the desktop
package, so the layer inversion remains. Useful as a *follow-on* to reduce
kernel internal coupling, not a substitute for extraction.

**Distribute the kernel as an installed package (`pip install`).** Strongest
boundary, but adds build/version friction inside one repo. Deferred to the
naming open question; a top-level in-repo package gets the boundary benefit
without the packaging cost.

## Validation

When this ADR moves to `accepted` and migration lands, the proof of force is
a dependency-direction assertion (extend `scripts/dev/ai_guardrail.py` or
add a dedicated check):

- Parse the module import graph and assert **no edge matches
  `^app\..* -> ^mediapipeline_desktop_app\.`** for the kernel-owned modules
  (and ultimately for all shared types).
- Assert the kernel package imports neither `app.*` nor
  `mediapipeline_desktop_app.*`.

Until that check exists, this ADR is a proposal only and is not enforced.

## Supersedes / superseded by

None. Extends ADR-0001 (folder-by-domain) and supports ADR-0010
(monolith-split campaign); does not supersede either.
