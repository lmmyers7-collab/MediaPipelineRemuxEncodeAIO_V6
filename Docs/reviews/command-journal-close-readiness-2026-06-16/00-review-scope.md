# Command Journal And Close Readiness Review Scope

Review date: 2026-06-16  
Branch observed: `refactor/mediapipeline-entrypoint-slice`  
Review type: exhaustive code review, documentation only  
Application code edited: no

## Request

Perform a full code review of command journal behavior, strict JSON mutation guards, duplicate-command protection, backend close-readiness, shutdown safety, active encode/process detection, Tauri close behavior, and Diagnostics/Command History trust.

The requested outputs are this review packet:

- `00-review-scope.md`
- `01-code-map.md`
- `02-invariants-and-boundaries.md`
- `03-risk-review.md`
- `04-test-coverage-review.md`
- `05-findings.md`
- `06-remediation-plan.md`
- `07-validation-plan.md`
- `08-final-review-summary.md`

## Severity Policy

Per the request, these classes are high severity by default:

- accidental mutation without the required explicit confirmation
- unsafe close during active work
- misleading command evidence that can cause operators to trust the wrong state

Medium severity is used for bounded but real evidence gaps, persistence/degradation visibility gaps, or validation gaps where production behavior is guarded but not fully exercised.

Low severity is used for documentation or UX trust issues that do not directly change backend behavior.

## Repo Instructions Followed

The review followed the repository instructions in `AGENTS.md`:

- Read `AGENTS.md`.
- Read `docs/CURRENT_PROJECT_STATE.md`.
- Read `docs/OPEN_WORK_CHECKLIST.md`.
- Read `docs/generated/PROJECT_INDEX.md`.
- Inspected generated summaries before full source when summaries existed.
- Kept this review under `docs/reviews/` instead of adding top-level markdown.
- Did not edit application code.
- Added a required unreleased change packet for the documentation work.

## Generated Summaries Inspected First

These generated summaries were checked before reading the corresponding full source:

- `docs/generated/summaries/src/mediapipeline/desktop/api/command_journal_policy.py.md`
- `docs/generated/summaries/src/mediapipeline/desktop/api/handler.py.md`
- `docs/generated/summaries/src/mediapipeline/desktop/api/handler_policy.py.md`
- `docs/generated/summaries/src/mediapipeline/core/processes/launch_runner.py.md`
- `docs/generated/summaries/apps/desktop/tauri/src-tauri/src/backend_process.rs.md`
- `docs/generated/summaries/src/mediapipeline/core/network/lifecycle_facade.py.md`

The summaries were mostly structural/metadata summaries, so full source was required for evidence.

## Surfaces Reviewed

Command recording:

- local API request handling
- strict JSON serialization behavior
- command-result journal policy
- bounded command history
- local UI command history fallback rows
- backend `/api/commands` payload
- Diagnostics/Command History evidence labels

Strict mutation guards:

- Pydantic route contracts for mutation endpoints
- `confirm_apply` and `confirm_save` requirements
- route metadata that suppresses journaling for secret-transfer or unjournaled commands
- facade-level confirmation checks before mutation

Duplicate-command protection:

- shared process launch lock
- active work blockers
- duplicate pipeline/audit/rerun launch behavior
- network lifecycle duplicate-start behavior where it overlaps command execution trust

Backend close-readiness:

- safe/unsafe close policy
- stale launch guard cleanup
- related process detection
- ActiveJobs process identity checks
- pipeline progress detection
- audit progress detection
- final-library promotion detection
- queue source scan detection
- schedule-stop watcher detection

Tauri close behavior:

- close readiness GET contract
- close confirmation path
- safe backend shutdown POST
- confirmed force backend shutdown POST
- process-tree termination fallback
- close handling for window close, destroyed, and app exit events

Diagnostics/Command History trust:

- source labeling of local vs backend journal rows
- dedupe behavior
- diagnostics target allowlist
- read-first/mutation-boundary messaging
- command stream success/failure caveats

## Out Of Scope

This review did not re-review every prior network coordinator/worker finding except where it directly overlaps command journal, mutation guards, duplicate-command protection, close-readiness, or Diagnostics trust.

This review did not intentionally run live media encodes or live Tauri GUI close tests. Those are called out in the validation plan because they are the remaining high-value validation path for close safety.
