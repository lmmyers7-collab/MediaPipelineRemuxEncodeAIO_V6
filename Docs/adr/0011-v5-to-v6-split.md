# 0011. Historical: V5 → V6 split

Status: historical
Date: 2026-05-28
Source: `Docs/archive/v6-split-notes-2026-05-20.md` (originally `V6_SPLIT_NOTES.md` at the repo root, dated 2026-05-20)

## Context

This ADR records, in durable form, the V5 → V6 split that produced the
current repository shape. The split was documented in
`V6_SPLIT_NOTES.md` at the repo root; that file is archived in this
session to `Docs/archive/v6-split-notes-2026-05-20.md` so per-feature
detail (specific validation commands, live-API verification) is not
lost. This ADR is the short, immutable record.

A new contributor reading the codebase will see two parallel
workspaces (V5 external as fallback; V6 internal as the active tree)
and reasonably ask why. The honest answer: V6 is the WebView-first
split that drops the legacy desktop GUI but keeps the working pipeline
and Tauri/WebView2 shell. V5 stayed alive as the rollback path until
V6's promotion gates clear.

## Decision

This ADR documents — it does not propose. The split occurred on
2026-05-20 and the decisions below are historical.

What the split did:

- Created the V6 workspace as a WebView-first carve-out of V5. V6
  contains: backend media policy (PowerShell modules under `Pipeline\`),
  Python local API, WebView assets, Tauri/WebView2 shell, docs, tests,
  smoke wrappers, bundled tools, and runtime dependencies needed to
  continue WebView/Tauri refinement work.
- Removed the legacy desktop GUI surface:
  - Root and desktop legacy GUI launchers.
  - `DesktopApp\mediapipeline_desktop_app\app.py`, `ui.py`, `widgets.py`,
    `workers.py`, `theme.py`, and the legacy GUI `controllers\` and
    `views\` packages.
  - Legacy PowerShell GUI launcher scripts under
    `Pipeline\MediaPipelineRemuxEncodeAIO_LegacyGUI.*`.
  - Legacy desktop-shell unit tests.
  - Copied legacy GUI framework site-package files from the V6 bundled
    Python runtime.
- Established what remained authoritative in V6:
  - Backend media policy stays in `Pipeline\` PowerShell modules and
    Python backend services.
  - WebView is a control, evidence, and monitoring surface only; it
    must not implement filesystem mutation, route decisions, queue
    inclusion policy, publish/drain safety, subtitle/audio policy, or
    output acceptance independently. (This rule is now codified in
    `AGENTS.md §3` and ADR-0006.)
  - Source media must not be mutated or deleted by default; scratch-
    copy-first behavior and pending-publish manifest evidence remain
    release-critical.
  - V5 is the external fallback for any operator flow not yet
    validated in V6.

Validation performed at the time of the split (2026-05-20) is the full
list preserved in the archived source notes. Headline result:
`1131 Python tests OK`, `21 Rust tests passed` in the Tauri build
gate. The local API at `http://127.0.0.1:11992` served
`/api/health` (`status=ok`, `app_version=v6.000`), `/api/contract`,
`/api/queue`, and the asset routes. Current V6 release validation now
runs the WebView/backend reliability wrapper by default; archived
legacy desktop-shell checks require the explicit
`-RunLegacyDesktopChecks` switch.

## Open follow-ups (carried from the source notes)

Recorded here so they remain visible after the source file is archived:

- Run representative real-media V6 pilot processing from the
  WebView/Tauri path.
- Build a clean deployable V6 package and run package-mode Tauri
  launch/close.
- Reconcile older V5/legacy-desktop historical docs only when they are
  touched for active work; archive-only docs can remain historical.

These are operational gates, not architectural decisions. They are
tracked in the relevant operator-facing docs (e.g. `AGENTS.md §9`
notes that Tauri/WebView2 as the production replacement is not yet
fully true pending PG-3 clean-machine and real-media validation).

## Consequences

Code and structure:

- The V6 tree as it exists today is the *result* of the split. There is
  no legacy desktop GUI to maintain in this repository.
- ADR-0006 (local API as the only operator surface) and ADR-0008
  (Tauri/WebView2 as the shell) codify the post-split operator surface
  and are in force.

Operational surface:

- V5 lives externally as the rollback path. This ADR is the durable
  pointer that the dual-workspace setup is intentional and time-bound.

Testing and CI:

- The `1131 tests OK` headline is a 2026-05-20 snapshot, not a
  standing claim. Current test counts evolve with the codebase.

Migration cost:

- Zero — this is a record, not a change.

Reversibility:

- Not applicable; historical.

## Alternatives considered

**Keep `V6_SPLIT_NOTES.md` as a living document.** The notes mix
durable rationale (what remained authoritative, what the split
removed) with one-time validation evidence (specific shell commands,
specific tokens, specific port numbers). As a living document the
one-time evidence stales fast; as an archive it stays accurate to
2026-05-20.

**Delete the source notes after writing this ADR.** Loses the
specific validation evidence and live-API proof, which are useful as a
known-good baseline if a future regression hunt asks "what worked on
the day of the split?". Rejected — archive instead.

**Inline every detail into this ADR.** Doubles ADR length without
adding decision content. Rejected.

## Validation

- `Docs/archive/v6-split-notes-2026-05-20.md` exists and contains the
  original 2026-05-20 text.
- ADR-0006 (operator surface) and ADR-0008 (shell) are accepted, so
  the post-split shape is in force.
- `AGENTS.md §3` codifies the WebView-as-control-only rule that this
  split established.

## Supersedes / superseded by

Supersedes (informally): the original `V6_SPLIT_NOTES.md` at the repo
root. The archived copy at `Docs/archive/v6-split-notes-2026-05-20.md`
is read-only history.
