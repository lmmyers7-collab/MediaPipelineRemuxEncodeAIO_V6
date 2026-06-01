# Dependency Refactor Phase Plan - Navigation and Tracker

Source plan: `Docs/rewrite/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`

Created: 2026-05-31

Purpose: split the dependency cleanup plan into smaller, sequential phase files
that a Codex agent can operate one at a time. This folder is a rewrite staging
area only. It does not replace `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
`OPEN_WORK_CHECKLIST.md`, or any generated project index.

The original source plan remains untouched. Do not implement the dependency
cleanup from this tracker unless the user explicitly asks you to operate a
specific phase.

## Operating Contract

Every implementation agent must repeat these steps at the start of each phase:

1. Read `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
   `OPEN_WORK_CHECKLIST.md`, and `Docs/generated/PROJECT_INDEX.md`.
2. Read this tracker and the active phase file.
3. Read the prior phase handoff before starting the next phase.
4. Check `summaries/<path>.md` before opening full source files.
5. Use the bundled Python interpreter:

   ```powershell
   .\DesktopApp\Runtime\Python\python.exe
   ```

6. Work only the current phase. Stop after the phase with a summary, validation
   evidence, and remaining risks.
7. Keep product behavior unchanged unless a later explicit task says otherwise.
8. Do not change media policy, queue behavior, publish/drain behavior, settings
   persistence, source/scratch/output movement, or WebView/Tauri ownership as
   part of dependency cleanup.
9. Do not create root `*_REPORT.md`, `*_FIXES.md`, `*_CHECKLIST.md`, or new
   single-source-of-truth documents.
10. Keep activity history in this tracker plus the phase file activity log.

## Phase Order

| Phase | Status | File | Operate After | Handoff To |
|---|---|---|---|---|
| 0 | Complete | [01_phase_0_baseline_and_dependency_guard.md](01_phase_0_baseline_and_dependency_guard.md) | Required repo first reads | Phase 1 |
| 1 | Complete | [02_phase_1_config_boundary.md](02_phase_1_config_boundary.md) | Phase 0 checker/report evidence | Phase 2 |
| 2 | Complete | [03_phase_2_status_observability_telemetry.md](03_phase_2_status_observability_telemetry.md) | Phase 0 checker/report evidence | Phase 3 |
| 3 | Complete | [04_phase_3_api_ui_boundary.md](04_phase_3_api_ui_boundary.md) | Phase 0 checker/report evidence | Phase 4 |
| 4 | Complete | [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md) | Phases 0-3 complete or deliberately deferred | Phase 5 |
| 5 | Complete | [06_phase_5_harden_dependency_rules.md](06_phase_5_harden_dependency_rules.md) | Prior cleanup results and known allowlist needs | Final review |
| Final | Dependency blockers closed; validation caveat recorded | [07_full_cleanup_review_and_done.md](07_full_cleanup_review_and_done.md) | Phases 0-5 complete | Resolve unrelated Web static smoke failure before claiming all tests green |

## Activity Log Rules

Use exact dates. Each phase should append to its own activity log and summarize
the same event here when it changes phase status.

Recommended entry format:

| Date | Agent | Phase | Action | Evidence | Next |
|---|---|---|---|---|---|
| 2026-05-31 | Codex | Split | Created phase files only | Original plan inspected; no implementation run | Start Phase 0 when requested |

## Central Activity Log

| Date | Agent | Phase | Action | Evidence | Next |
|---|---|---|---|---|---|
| 2026-05-31 | Codex | Split | Created this split-plan folder from `CODEX_DEPENDENCY_REFACTOR_PLAN (1).md` | Added tracker, six phase files, and final review file; original plan not modified | Operate `01_phase_0_baseline_and_dependency_guard.md` only when requested |
| 2026-05-31 | Codex | 0 | Completed report-only dependency boundary baseline tooling | Added `scripts/dev/check_dependency_boundaries.py`, focused tooling tests, architecture rules doc, refreshed summaries for new tooling, and regenerated `Docs/generated/PROJECT_INDEX.md`; checker reports 1407 internal app import entries, 1 module cycle, 2 package cycles, and current shared/config/API/status findings | Start `02_phase_1_config_boundary.md` when requested |
| 2026-05-31 | Codex | 1 | Completed `app.config` boundary cleanup | Moved settings patch preview facade to `app.orchestration`, moved `EffectiveDecisionPolicy` to `app.contracts`, regenerated summaries/index artifacts, and checker reports 0 forbidden `app.config` higher-level imports with the config/orchestration package cycle gone | Start `03_phase_2_status_observability_telemetry.md` when requested |
| 2026-05-31 | Codex | 2 | Completed status/observability/telemetry direction cleanup | Moved status facade ownership to `app.status`, moved system metric sampling to `app.telemetry`, regenerated summaries/index artifacts, and checker reports 0 package-level cycles plus 0 status/telemetry direction violations | Start `04_phase_3_api_ui_boundary.md` when requested |
| 2026-05-31 | Codex | 3 | Completed API/UI preference boundary cleanup | Moved neutral UI preference persistence to `app.ui_preferences`, updated API preference routes to import the neutral owner, regenerated summaries/index artifacts, and checker reports 0 forbidden `app.api` to `app.ui` imports | Start `05_phase_4_shared_blast_radius.md` when requested |
| 2026-05-31 | Codex | 4A | Completed schedule constants shared-reduction sub-phase | Moved `SCHEDULE_DAY_NAMES` to `app.schedule.constants`, refreshed summaries, and checker reports `app.shared.constants` imports dropped from 38 to 36 with package cycles still 0 | Continue Phase 4 with another scoped sub-phase before Phase 5 |
| 2026-05-31 | Codex | 5 | Completed dependency-rule hardening | `check_dependency_boundaries.py` now fails on unallowlisted hard-rule findings by default, `ai_guardrail.py` runs it in preflight/postflight, and the existing source-media module cycle has 10 specific allowlist entries | Start `07_full_cleanup_review_and_done.md` when requested |
| 2026-05-31 | Codex | Final | Completed final review audit; full definition of done remains open | Phase handoffs read, phase links checked, and Phase 5 validation commands pass; checker reports 0 package cycles and 0 unallowlisted hard findings, but the `source_media` module cycle remains allowlisted and Phase 4 shared warning surfaces remain | Resume Phase 4 shared reduction, remove the source-media allowlist after refactor, then rerun final review |
| 2026-05-31 | Codex | 4B | Completed audit rerun shared-reduction sub-phase | Moved audit rerun CSV columns, audit-specific protocols, and audit rerun file IO helpers to `app.audit`; checker reports `app.shared.utils` 32 -> 27, `app.shared.constants` 36 -> 35, and `app.shared.protocols` 19 -> 16 with package cycles still 0 | Continue Phase 4 with another scoped sub-phase, then rerun final review |
| 2026-05-31 | Codex | 4C | Completed status read-model shared-reduction sub-phase | Moved status JSON/tail helpers and status-specific protocols to `app.status`; checker reports `app.shared.utils` 27 -> 22 and `app.shared.protocols` 16 -> 14 with package cycles still 0 | Continue Phase 4 with another scoped sub-phase, then rerun final review |
| 2026-05-31 | Codex | 4D | Completed protocol ownership shared-reduction sub-phase | Moved remaining direct `app.shared.protocols` consumers to domain contract modules; checker reports `app.shared.protocols` 14 -> 0 with package cycles still 0 | Continue Phase 4 with config constants sub-phase, then rerun final review |
| 2026-05-31 | Codex | 4E | Completed config constants shared-reduction sub-phase | Moved config option/profile constants to `app.config.constants` and schema-version imports to `app.contracts.config`; checker reports `app.shared.constants` 35 -> 24 with package cycles still 0 | Continue Phase 4 with process runtime state sub-phase, then rerun final review |
| 2026-05-31 | Codex | 4F | Completed process runtime state shared-reduction sub-phase | Moved process constants to `app.processes.constants` and process JSON/text helpers to `app.processes.file_io`; checker reports `app.shared.utils` 22 -> 16 and `app.shared.constants` 24 -> 17 with package cycles still 0 | Continue Phase 4 with queue ownership sub-phase, then rerun final review |
| 2026-05-31 | Codex | 4G | Completed queue ownership shared-reduction sub-phase | Moved queue dry-run atomic snapshot write helper to `app.queue.file_io`; checker reports `app.shared.utils` 16 -> 15 with package cycles still 0 | Continue Phase 4 with publish pending reads sub-phase, then rerun final review |
| 2026-05-31 | Codex | 4H | Completed publish pending reads shared-reduction sub-phase | Moved pending-publish manifest and drain-summary JSON reads to `app.publish.file_io`; checker reports `app.shared.utils` 15 -> 13 with package cycles still 0 | Continue Phase 4 with rename ownership sub-phase, then rerun final review |
| 2026-05-31 | Codex | 4I | Completed rename ownership shared-reduction sub-phase | Moved rename sidecar/filter constants to `app.rename.constants` and rename atomic writes to `app.rename.file_io`; checker reports `app.shared.utils` 13 -> 10 and `app.shared.constants` 17 -> 14 with package cycles still 0 | Continue Phase 4 with file opening and media constants sub-phase, then rerun final review |
| 2026-05-31 | Codex | 4J | Completed file opening and media constants shared-reduction sub-phase | Moved file-open path helpers to `app.files.opening` and media/VLC constants to `app.files.constants`; checker reports `app.shared.utils` 10 -> 8 and `app.shared.constants` 14 -> 5 with package cycles still 0 | Continue Phase 4 with folder policy, failure, storage, and app-state sub-phase, then rerun final review |
| 2026-05-31 | Codex | 4K | Completed folder policy, failure, storage, and app-state shared-reduction sub-phase | Moved folder-policy constants/helpers, failure manifest constants/writes, storage app-state name, and schedule app-state helpers into owning domains; checker reports `app.shared.constants` 5 -> 0 and `app.shared.utils` 8 -> 3 with package cycles still 0 | Continue Phase 4 with final shared shrink, then rerun final review |
| 2026-05-31 | Codex | 4L | Completed final shared-shrink sub-phase | Moved settings-save/open-path helpers to `app.config.file_io`, release manifest reads to `app.maintenance.file_io`, redirected desktop compatibility imports to domain owners, and retired shared modules; checker reports `app.shared.utils` 3 -> 0 with package cycles still 0 | Rerun final cleanup review after Phase 4 completion |
| 2026-05-31 | Codex | Final | Reran final review after Phase 4 completion; full definition of done remains open | Phase handoffs read, phase/sub-phase links checked, Phase 5 validation commands pass, and checker reports 0 direct `app.shared*` imports plus 0 package cycles; DoD remains open because the `source_media` module cycle is still allowlisted and barrel re-export warnings remain | Refactor the `source_media` module cycle, resolve or explicitly accept barrel re-export warnings, then rerun final review |
| 2026-05-31 | Codex | Final | Closed remaining dependency-checker DoD blockers | Split source-media models into `app.contracts.source_media_models`, preserved the public `app.contracts.source_media` import path, removed source-media allowlist rows, retired package barrel re-exports, and checker reports 0 module cycles, 0 package cycles, 0 direct `app.shared*` imports, 0 allowlisted hard findings, 0 unallowlisted hard findings, and 0 warning findings | Resolve the unrelated Web static smoke assertion in `DesktopApp/tests/test_application_facade_local_api.py` before marking every validation target green |

## Phase Completion Handoff Template

Each phase should end with a handoff in the active phase file using this shape:

```text
Phase:
Status:
Files changed:
Behavior changes:
Checks run:
Dependency checker result:
Generated artifacts updated:
Summaries refreshed:
Known risks:
Explicit deferrals:
Next phase:
```

## Traceability Expectations

- Every phase file links to its previous and next file.
- Every phase repeats the operating contract enough that an agent can start from
  that file without drifting from the project rules.
- Activity logs stay close to the work: central summary here, detailed log in
  the phase file.
- If a phase is split further, create sub-phase notes under this same folder and
  link them from the owning phase. Do not create repo-root planning files.
- If source edits happen later, refresh summaries for touched source files or
  record why summary refresh could not be run.
