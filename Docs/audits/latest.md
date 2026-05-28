---
updated: 2026-05-28
source: ARCHITECTURAL_OVERHAUL_PLAN.md §Current-State Audit
scope: V6 main branch, post Phase 0 / Phase 1 scaffolding
status: advisory — known issues, not blocking
---

# Latest audit — known issues

This file is the "known issues" register referenced by `CLAUDE.md`
startup. Items here are real but not stop-the-world. If you're about
to touch one of these areas, read the listed item before making
changes.

When this file's `updated:` date is older than 7 days, treat the
findings as advisory only and flag the staleness in your handoff.
Refresh it whenever a finding lands or a new structural issue is
discovered.

For active per-area audits, see `Docs/audits/` siblings
(e.g. `CODE_REVIEW_V5_WEBVIEW_TAURI_AUDIT.md`,
`DEAD_EXPORT_AUDIT_2026-05-19.md`).

## Top-level structural findings

### F-001 — Service/facade fragmentation (open, Phase 6)

108 `service_*.py` plus 65 `facade_*.py` plus
`command_payloads_*.py` siblings under
`DesktopApp/mediapipeline_desktop_app/`. Settings alone spans 22+
sibling files. The plan's Phase 6 folds these into `app/<domain>/`
packages; ADR-0001 establishes the target shape and the
forbidden-suffix list.

**Action when touching**: prefer `app/<domain>/` for new code; do not
add new files at the legacy flat paths (`AGENTS.md §2` enforces this).

### F-002 — PowerShell modules with dotted suffixes (open, Phase 3)

168 `.ps1` files under `Pipeline/Modules/` named like `Audit.Audio.ps1`
and `Subtitles.Common.Config.ps1`. Phase 3 folds them into
`engine/<domain>/<role>.ps1` behind `engine/entrypoint.ps1` per
ADR-0002.

**Action when touching**: do not add new dotted-suffix PowerShell
files; if a new module is needed, write it into the target
`engine/<domain>/` location and have it loaded by `entrypoint.ps1`.

### F-003 — Three config representations, no generator (open, Phase 2)

`Pipeline/MediaPipeline_config_chatgpt.psd1` (authoritative runtime
config), `config_schema.py` + 4 siblings (Python representation),
WebView JSON (third representation). No shared schema generator.
ADR-0004 makes `app/contracts/config.py` the source of truth and lands
schema generation in Phase 2 / Phase 4.

**Action when touching**: add fields to `app/contracts/config.py`
first; mirror into PSD1 template; WebView consumer updates from the
generated schema.

### F-004 — JSON state files, no DB (open, Phase 4)

State today is ~10 distinct JSON files under `LocalBase/State/`. No
filtering by age/status; concurrent writes can race; partial writes
can corrupt. ADR-0003 moves this to `state/state.sqlite`.

**Action when touching**: keep changes write-compatible with the
current JSON readers; do not introduce new JSON state files for new
features — wait for `app/storage/db.py`.

### F-005 — Unstructured logs, log-scraping Diagnostics (open, Phase 4)

PowerShell run logs are plain text; Diagnostics re-parses them.
Fragile and slow. ADR-0005 establishes JSON Lines on every log producer
and an `events` table in SQLite.

**Action when touching**: when adding new log lines in Python, use
structured logging if possible; in PowerShell, prefer one of the
existing helper patterns over `Write-Host`.

### F-006 — 1:1 test mapping (open, Phase 5)

`tests/test_facade_<name>.py` and `tests/test_service_<name>.py` mirror
the flat tree 1:1. The plan's Phase 5 collapses these into
behavior-grouped tests under `tests/python/{unit,integration,contract}/`.

**Action when touching**: when adding a new test, organize by
behavior; do not start a new 1:1 mapping for a new file.

## Documentation findings

### F-010 — `MONOLITH_SPLIT_PLAN.md` (141 KB) is over-large (open, Phase 7)

Campaign is complete; the doc has become a drift surface. ADR-0010
records the historical summary so the original can be archived.

### F-011 — `AI_HANDOFF.md` (107 KB) historical (open, Phase 7)

Superseded by `AGENTS.md`. Plan §Debloat marks it for archive.

### F-012 — `md_documentation_audit*` (223 KB + 43 KB) one-shot artifacts (open, Phase 7)

CSV + report. Plan §Debloat marks them for deletion (CSV) and archive
(report).

### F-013 — `CLAUDE.md` references `Docs/audit/latest.md` (this file) but tree uses `Docs/audits/` (resolved 2026-05-28)

`CLAUDE.md` says `Docs/audit/latest.md` (singular); the existing
directory is `Docs/audits/` (plural). Resolved by placing this file at
`Docs/audits/latest.md`. `CLAUDE.md` text mismatch is logged; left
unchanged this session to avoid editing the governing file.

## Repo-state findings

### F-020 — Uncommitted churn parked in stash, now also in branch (resolved 2026-05-28)

`stash@{0}` (label `pre-overhaul-WIP-snapshot-2026-05-28`) holds
~200 modified files from a prior doc-cleanup pass that did not land.
Branch `pre-overhaul-snapshot` was created from the stash this session
as a passive archive. **Do not pop the stash and do not merge the
branch** — both are recovery anchors.

### F-021 — Vendored PowerShell 7.6 on disk (advisory)

`Pipeline/PowerShell-7.6.0-win-x64/` is gitignored but the directory
still exists locally. Verify with
`git ls-files Pipeline/PowerShell-7.6.0-win-x64/` (expected empty). If
ever committed historically, repo history would carry the weight.

### F-022 — `Pipeline/__pycache__/` directory may exist (advisory)

Plan flags this as committed at some point. Verify with
`git ls-files Pipeline/__pycache__/` (expected empty). If not empty,
the cleanup belongs in Phase 6.

## Known-good baselines

- Tag `v6-pre-overhaul` (commit `8d6d9f6`) is the deepest rollback
  point.
- `app/contracts/config.py` and `app/contracts/stages.py` exist as the
  ADR-0001 / 0004 anchors (commit `77b8b4c`).
- 540 summaries under `summaries/` keep AI context cheap.

## Schema

```yaml
updated: ISO-8601 date (UTC)
source: pointer to the upstream audit / plan
scope: what this audit covers
status: advisory | active | blocking
```

Findings are numbered `F-NNN`. Numbers do not reset across audit
refreshes — finding `F-005` is the same area on every refresh; either
the finding moves to `(resolved ...)` or its body updates with the
latest status.
