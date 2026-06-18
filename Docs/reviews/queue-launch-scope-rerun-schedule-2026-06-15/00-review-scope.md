# Queue Launch Scope, CSV Rerun, Schedule, Duplicate Guard, and Active Job Review Scope

Review date: 2026-06-16

Change packet: `ops/release/changes/unreleased/MP-CHANGE-2026-0615-019.json`

## Request

Perform a full code review of the paths that can launch work, rerun CSV rows, start and stop scheduled work, prevent duplicate commands, journal commands, and decide whether active work is in progress. The explicit concern is any path that could process the wrong file, start twice, ignore selected-vs-filtered scope, or mislead the operator about what will run.

## Method

This review followed `AGENTS.md`:

- Read required project state files before source: `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, and `docs/generated/PROJECT_INDEX.md`.
- Inspected generated summaries before full source for the affected modules.
- Reviewed source and tests only. No production code was changed.
- Created review artifacts under `docs/reviews/`, not the repository root.
- Created a change packet for the docs-only review work.

## Reviewed Areas

- Queue preview and launch scope: backend queue plan, dry-run queue plan emission, source scan state, UI selected/filter state, and queue-to-launch wording.
- Which files can launch: queued pipeline launch, single-file launch, CSV rerun launch, audit launch, and control actions.
- Priority behavior: high, normal, low, hold, manifest writes, and source-root validation for priority writes.
- CSV rerun interpretation: exported columns, row enablement, row policy overrides, source identity checks, duplicate planned-output checks, dry-run manifest behavior, and WebView launch request shape.
- Schedule start and stop: schedule gate, run-once override, ignore override, continuous schedule-stop watcher, close-readiness exposure, and stop flag write.
- Stop controls: Stop After Current, Pause/Resume, Rescan, and Force Stop.
- Duplicate-command guards: launch lock, control lock, related process scan, ActiveJobs state, queue source scan duplicate handling, and stale launch guard cleanup.
- Active-job behavior: launch record creation, heartbeat/completion watchers, close blockers, PID verification, and stale/unverifiable PID handling.
- Command journaling: command result persistence, validation-failure journaling, request capture, bounded evidence, and secret redaction.

## Non-Goals

- No code remediation was implemented.
- No UI redesign was implemented.
- No source behavior was changed.
- No media processing command was executed.

## Primary Verdict

The queue, schedule, duplicate launch, ActiveJobs, priority, and command-journal surfaces are generally strong and evidence-rich. Three gaps need remediation:

1. High: single-file launch accepts an arbitrary existing local file and bypasses configured source-root scope.
2. Medium: WebView CSV rerun starts live rerun by default and exposes no UI dry-run evidence path, even though backend dry-run support exists.
3. Medium: Force Stop operator wording understates backend scope because the backend kill path can terminate pipeline, audit, and CSV rerun PowerShell processes.
