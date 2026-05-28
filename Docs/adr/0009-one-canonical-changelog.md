# 0009. One canonical CHANGELOG; PR descriptions are not docs

Status: accepted
Date: 2026-05-28

## Context

The repository has accumulated multiple change-log-shaped documents:

- `Docs/CHANGELOG_SUMMARY.md`
- `Docs/DOC_TOUCH_LOG.md`
- Per-feature implementation reports —
  `COORDINATOR_WORKER_NETWORK_PROMOTION_IMPLEMENTATION_REPORT.md`,
  `COORDINATOR_WORKER_PHASE26_*REPORT.md`,
  `OBSERVABILITY_AND_SECRETS_FIXES.md`,
  `SETTINGS_WIZARD_REVIEW_FIXES.md`, and others.
- Status documents (`Docs/CURRENT_PROJECT_STATE.md`,
  `OPEN_WORK_CHECKLIST.md`, `AI_HANDOFF.md`) that include change
  narrative.

None of them is the authoritative change record. `git log` is, but no
human reads `git log` for a release summary. The proliferation of
per-feature `_REPORT.md` files is the symptom: PR descriptions are
being committed into the repo because there is no obvious place to
write a release-grade summary.

## Decision

`CHANGELOG.md` at the repo root is the **single** canonical changelog.
It uses the [keepachangelog](https://keepachangelog.com/) format.

Rules in force:

- **Only `CHANGELOG.md`.** No second changelog, no per-feature
  `_REPORT.md` at the repo root, no `_FIXES.md` at the repo root.
- **PR descriptions live in PRs.** Not in the repo. If a PR's intent
  is worth keeping, it goes into `CHANGELOG.md` (operator-facing
  summary) and/or an ADR (architectural decision).
- **Pre-commit warns** when `app/`, `engine/`, or `schemas/` change but
  `CHANGELOG.md` does not. The check is a warning, not a block;
  `[no-changelog]` in the commit message opts out cleanly (rare cases
  such as pure refactors or test-only PRs).
- **`Unreleased` section** at the top accumulates entries between
  releases. On release, the maintainer renames `Unreleased` to a
  version + date and starts a new `Unreleased`.
- **Sections** within each version: `Added`, `Changed`, `Deprecated`,
  `Removed`, `Fixed`, `Security`. Skip sections that have no entries.

What goes in `CHANGELOG.md`:

- User-visible behavior changes.
- Operator-visible behavior changes (CLI / API / WebView).
- Migrations and breaking changes (with the migration path).
- Important ADR landings (link the ADR).

What does **not** go in:

- Refactors that do not change behavior.
- Pure test additions.
- Documentation cleanup.
- Internal renames.

These are visible in `git log` and do not need a release-level entry.

## Consequences

Code and structure:

- The existing `Docs/CHANGELOG_SUMMARY.md` is archived into
  `Docs/archive/` (Phase 7) and the new `CHANGELOG.md` absorbs the
  forward-looking entries.
- `Docs/DOC_TOUCH_LOG.md` is deleted; `git log` is the touch log.
- Per-feature `*_REPORT.md` at the repo root are deleted (their
  content is in commit messages; if it isn't, the commit message gets
  rewritten or amended into the PR description).

Operational surface:

- One file to read before a release. One file to grep for "when did
  this land".

Testing and CI:

- Pre-commit warning hook. CI does not block on it.

Migration cost:

- One-time cleanup pass during Phase 7. The deletions are reversible
  via `git revert`.

Reversibility:

- High. Reverting this ADR means adding more changelogs back. There's
  no technical lock-in.

## Alternatives considered

**Generate changelog from conventional commits.** Requires every
commit to follow a strict format; the project does not enforce that
and historical commits do not match. Rejected.

**Keep per-feature reports as a `Docs/changelogs/` directory.**
Solves the "where" question but creates 30+ files per release. The
keepachangelog single-file format scales better at this size.
Rejected.

**Use GitHub Releases as the canonical changelog.** The project is
single-operator and may ship outside GitHub. Rejected.

## Validation

- `CHANGELOG.md` exists at the repo root.
- Pre-commit hook `changelog-touched.py` (Phase 5 — planned) warns on
  uncovered code changes.
- A grep at release time: `Get-ChildItem -Path . -Filter "*_REPORT.md" -File`
  at the repo root returns nothing.
