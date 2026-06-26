# Findings

## Finding 1 - High - Single-file launch can process an arbitrary existing local file outside configured source roots

Status: open

Affected surface:

- WebView pipeline start
- `/api/pipeline/start`
- `build_pipeline_launch_plan()`
- `MediaPipeline.ps1 -SingleFile`

Evidence:

- `apps/desktop/webview/static/assets/launch/startRequest.js:20-33` collects `single_file` from a free-text input and adds it to the launch request.
- `src/mediapipeline/core/processes/pipeline_facade.py:124` passes `single_file` through to the service without source-root validation.
- `src/mediapipeline/core/processes/launch_plans.py:65` appends `-SingleFile` to the PowerShell command.
- `ops/pipeline/entrypoints/MediaPipeline.ps1:594-604` only checks that the single-file path exists.
- `ops/pipeline/entrypoints/MediaPipeline.ps1:622-629` resolves media kind and calls `Invoke-MediaPipelineProcessFile`.
- `ops/pipeline/engine/shared/path_helpers.ps1:216-287` falls back to `default_movie` with empty root when the file is not under configured movie/TV roots and no TV pattern matches.
- Existing tests assert pass-through behavior rather than source-root rejection, for example `tests/python/desktop/test_application_facade_process_launch.py` and `tests/python/desktop/test_service_process_launch_plans.py`.

Why this matters:

Normal queue launch scope is backend-owned and based on configured sources. Priority updates already enforce configured source roots through `validate_queue_source_path()`. Single-file launch bypasses that boundary and can process any existing local file path that the app process can see. This can process the wrong file, classify it as a default movie, and mislead the operator into thinking configured source-root and queue-scope protections still apply.

Recommended remediation:

- Add backend validation before `start_pipeline()` accepts `single_file`.
- Require an absolute path, existing leaf file, supported media suffix, and containment under configured `SourceMovies`, `SourceTV`, or enabled library profile source roots.
- Return a blocking command result when validation fails and journal the rejected request with redacted/bounded path evidence.
- Add preflight evidence for accepted single-file requests: matched source root, media kind, and reason.
- Add tests for outside-root rejection, under-root acceptance, non-file rejection, relative path rejection, and command-journal evidence.

## Finding 2 - Medium - WebView CSV rerun has no dry-run control or dry-run evidence path and hard-codes live launch

Status: open

Affected surface:

- WebView CSV rerun controls
- `/api/rerun/start`
- CSV rerun operator evidence

Evidence:

- `apps/desktop/webview/static/partials/page-launch.html:344-363` exposes CSV path, fixed copy/keep/park labels, and `Start CSV Rerun`, but no dry-run control.
- `apps/desktop/webview/static/assets/launch/startRequest.js:44-52` hard-codes `dry_run: false`.
- `apps/desktop/webview/static/assets/launchView.js:1418-1452` confirms and submits `/api/rerun/start` as a live rerun.
- Backend dry-run support exists: `src/mediapipeline/core/processes/launch_plans.py:170` appends `-DryRun`.
- Script dry-run evidence exists: `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1:732-735` writes manifest dry-run metadata and `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1:751-754` marks `dry_run_complete` and exits before staging.

Why this matters:

CSV rerun is driven by a CSV path supplied by the operator. The backend script has strong row-level safeguards, but the UI does not provide the operator a dry-run proof step before live staging/nested pipeline execution. This can mislead operators about what will run and makes CSV rerun less evidence-rich than queue launch.

Recommended remediation:

- Add a WebView "Preview CSV Rerun" dry-run action or a dry-run toggle that defaults to dry-run.
- Display manifest path, `dry_run_complete` status, planned row count, failed row count, duplicate planned-output failures, and unsafe override failures.
- Require explicit live confirmation after dry-run evidence, ideally binding the live request to the reviewed CSV path and manifest timestamp/hash.
- Add tests for dry-run request shape, live request shape, preflight rendering, and command journal evidence.

## Finding 3 - Medium - Force Stop wording understates backend termination scope

Status: open

Affected surface:

- Launch control buttons
- `/api/process/control` action `kill`
- Related PowerShell process termination

Evidence:

- `src/mediapipeline/core/processes/control_facade.py:148-156` calls `kill_related_pipeline_processes(resolved)` without a job-kind filter.
- `src/mediapipeline/core/processes/kill.py:105-113` includes pipeline, audit, and rerun script paths when `job_kinds` is omitted.
- `tests/python/desktop/test_service_process_kill.py` includes coverage that an audit process can be killed by the broad related-process kill path.
- UI command text in `apps/desktop/webview/static/assets/launch/commandButtons.js` describes Force Stop in pipeline terms.

Why this matters:

The backend behavior may be intentional as an emergency stop. The operator-facing wording does not make the broad scope explicit. If audit or CSV rerun work is active, Force Stop can terminate more than the operator expects and leave partial evidence or incomplete manifests.

Recommended remediation:

Choose one model and make code, UI, and tests agree:

- Scoped model: pass `job_kinds={"pipeline"}` for the pipeline Force Stop button and add a separate "Emergency Stop All" control for pipeline/audit/rerun.
- Broad model: keep the backend behavior, but rename/copy the UI to state that Force Stop terminates related pipeline, audit, and CSV rerun PowerShell processes.

In either case, journal the requested stop scope and actual killed process kinds.
