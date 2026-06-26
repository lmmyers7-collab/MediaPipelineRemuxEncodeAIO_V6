# Remediation Plan

This plan is intentionally scoped to the three open findings and the review boundaries. It avoids unrelated refactors.

## P0 - Constrain Single-File Launch to Configured Source Roots

Goal:

- Prevent `single_file` from processing arbitrary local files outside configured source roots.

Implementation steps:

1. Add a backend validator for pipeline `single_file`.
   - Reuse or generalize `validate_queue_source_path()` so the same configured-root boundary applies to single-file launch.
   - Require absolute path, existing leaf file, supported media suffix, and containment under `SourceMovies`, `SourceTV`, or enabled library profile source roots.

2. Apply validation before process launch.
   - The best boundary is before `service.start_pipeline()` in `start_pipeline_process()` or in a shared pipeline start request normalizer used by both preflight and start.
   - Rejected requests should return `ok: false`, severity `error` or `warning`, and a message that states the configured source-root scope.

3. Add preflight evidence.
   - Accepted single-file requests should show matched root, media kind, and match reason.
   - Outside-root single-file requests should be blocked before the Start button can be treated as ready-looking.

4. Preserve command journaling.
   - Journal blocked requests with bounded path evidence.
   - Avoid logging secrets or unbounded request data.

Tests:

- `single_file` outside configured roots is rejected by API/facade start.
- `single_file` outside configured roots is rejected by backend preflight.
- Relative path is rejected.
- Missing path is rejected.
- Directory path is rejected.
- Non-media suffix is rejected if media suffix policy exists for this launch surface.
- Under-root movie path is accepted and reports movie root evidence.
- Under-root TV path is accepted and reports TV root evidence.
- Command journal records rejected request without leaking sensitive evidence.

Acceptance criteria:

- No existing local file outside configured source roots can reach `MediaPipeline.ps1 -SingleFile`.
- Existing queued launch behavior is unchanged.
- Existing priority source-root validation semantics remain unchanged.

## P1 - Add CSV Rerun Dry-Run Evidence Flow to WebView

Goal:

- Make CSV rerun evidence-first and prevent operators from launching live rerun without seeing what the CSV will do.

Implementation steps:

1. Add a dry-run action.
   - Prefer a dedicated "Preview CSV Rerun" button that sends `dry_run: true`.
   - Keep "Start CSV Rerun" for live execution, but make live state visibly distinct.

2. Display dry-run manifest evidence.
   - Manifest path.
   - Manifest status.
   - CSV path.
   - `dry_run_complete`.
   - Planned row count.
   - Failed row count.
   - Duplicate output failures.
   - Unsafe policy override failures.
   - Source identity failures.

3. Add a live confirmation boundary.
   - Require explicit live confirmation after dry-run evidence.
   - Prefer binding live launch to the CSV path and dry-run manifest timestamp/hash when possible.

4. Preserve safe policy copy.
   - Continue to make WebView-supported policy copy/keep/park.
   - If row-level overrides are displayed, clearly show that unsafe row overrides are rejected.

Tests:

- WebView request collector can send `dry_run: true`.
- Dry-run button posts `/api/rerun/start` with `dry_run: true`.
- Live button posts `dry_run: false` only after explicit confirmation.
- Preflight/rendering displays dry-run manifest status and row counts.
- Command journal records dry-run and live rerun requests distinctly.
- Backend unit tests still reject unsafe stage/original/return modes.

Acceptance criteria:

- The operator can produce and inspect CSV rerun dry-run evidence from WebView.
- Live CSV rerun is not visually equivalent to dry-run.
- Existing backend copy/keep/park safety remains unchanged.

## P1 - Align Force Stop Scope, UI Copy, and Journal Evidence

Goal:

- Ensure Force Stop terminates exactly what the operator expects, or explicitly states that it is broad emergency termination.

Choose one model:

## Option A - Scoped Force Stop

- Pass `job_kinds={"pipeline"}` for the existing pipeline Force Stop control.
- Add a separate emergency control for all related pipeline/audit/rerun processes.
- Label the emergency control with the broader scope.

## Option B - Broad Emergency Force Stop

- Keep `kill_related_pipeline_processes(resolved)` without job-kind filter.
- Rename/copy the control so it states it terminates related pipeline, audit, and CSV rerun PowerShell processes.

Shared steps:

1. Include requested kill scope in the command result.
2. Include actual killed process job kinds/PIDs where available.
3. Journal the requested and actual kill scope.
4. Add tests for UI copy/request payload or command result evidence.

Acceptance criteria:

- Code, UI text, tests, and journal evidence agree about Force Stop scope.
- An operator can reconstruct what was requested and what was killed.

## P2 - Add Contract Tests for Scope Communication

Goal:

- Lock in important negative contracts so future UI/API changes do not accidentally make selected rows or filters look launch-authoritative.

Tests:

- Pipeline start request collector does not include Queue filters, selected rows, or visible-row IDs.
- Launch scope reconciliation renders a warning when Queue filters are active.
- Backend preflight/start remains final authority even when local UI scope rows look ready.
- Queue source scan still only supports `scope=all` unless a new backend-scoped scan mode is deliberately added.

Acceptance criteria:

- Selected-vs-filtered scope stays explicit and test-backed.

## P2 - Strengthen Active-Work Fallback Tests

Goal:

- Keep duplicate-start and close-readiness behavior robust when one evidence source is missing.

Tests:

- Related process scan unavailable plus ActiveJobs unavailable blocks or reports fail-closed.
- Fresh progress with active stage and `StopRequested=True` is evaluated with related process/ActiveJobs fallbacks.
- Stale launch guards are cleaned without allowing a live related process to be ignored.

Acceptance criteria:

- No single stale/missing state source can cause a duplicate launch when another active-work source is available.
