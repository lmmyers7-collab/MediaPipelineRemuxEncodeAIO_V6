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
| 0 | Not started | [01_phase_0_baseline_and_dependency_guard.md](01_phase_0_baseline_and_dependency_guard.md) | Required repo first reads | Phase 1 |
| 1 | Not started | [02_phase_1_config_boundary.md](02_phase_1_config_boundary.md) | Phase 0 checker/report evidence | Phase 2 |
| 2 | Not started | [03_phase_2_status_observability_telemetry.md](03_phase_2_status_observability_telemetry.md) | Phase 0 checker/report evidence | Phase 3 |
| 3 | Not started | [04_phase_3_api_ui_boundary.md](04_phase_3_api_ui_boundary.md) | Phase 0 checker/report evidence | Phase 4 |
| 4 | Not started | [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md) | Phases 0-3 complete or deliberately deferred | Phase 5 |
| 5 | Not started | [06_phase_5_harden_dependency_rules.md](06_phase_5_harden_dependency_rules.md) | Prior cleanup results and known allowlist needs | Final review |
| Final | Not started | [07_full_cleanup_review_and_done.md](07_full_cleanup_review_and_done.md) | Phases 0-5 complete | Close cleanup |

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
