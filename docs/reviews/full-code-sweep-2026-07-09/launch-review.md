# Launch workflow review — 2026-07-09

## Executive assessment

The Launch tab is architecturally aligned with the backend-ownership model. The WebView stages intent, renders backend preflight/readiness and command evidence, and posts only documented backend routes. Python owns request dispatch, launch and control locks, source-root validation, ActiveJobs/close-readiness checks, journaling, and PowerShell process spawning. PowerShell owns queue processing, scratch copying, remux/encode routing, and publish/park behavior.

Two backend contract defects prevent a clean approval. Most importantly, an authenticated empty `POST /api/pipeline/start` can start a real `once` run because `mode` is optional at the API boundary and is defaulted to `once` below it. There is no P0 finding.

| Severity | Count | IDs |
|---|---:|---|
| P0 | 0 | — |
| P1 | 1 | CSW-2026-07-09-LAUNCH-001 |
| P2 | 1 | CSW-2026-07-09-LAUNCH-002 |
| P3 | 0 | — |

## Workflow traces

### 1. Scope and source selection

1. The Launch form collects only `mode`, `sleep_seconds`, display flags, schedule override, and an optional `single_file`; it does not submit Queue display filters or selected Queue rows ([startRequest.js:19-32](../../apps/desktop/webview/static/assets/launch/startRequest.js)).
2. The WebView’s file browser is backend-owned (`POST /api/pipeline/browse-file`) and stages only the returned path ([launchView.js:970-1025](../../apps/desktop/webview/static/assets/launchView.js)). The browser route itself accepts only file selection and validates absolute existence, file type, and supported suffix ([commands_process.py:90-165](../../src/mediapipeline/core/api/commands_process.py)).
3. Start repeats source validation: `single_file` is required to be under configured source roots, exist, be a regular file, and have an allowed media suffix ([source_path_policy.py:98-168](../../src/mediapipeline/core/processes/source_path_policy.py)); the launch facade rejects any failing validation before spawn ([pipeline_facade.py:89-102](../../src/mediapipeline/core/processes/pipeline_facade.py)).
4. PowerShell processes the selected source through `Ensure-ScratchCopy` before encode or remux work ([encode_preflight.ps1:7-13](../../ops/pipeline/engine/process/encode_preflight.ps1), [remux_preflight.ps1:7-13](../../ops/pipeline/engine/process/remux_preflight.ps1)).

### 2. Preflight and capability evidence

`GET /api/launch/preflight` is backend-authored and returns normalized intent plus operator readiness; it does not reserve a launch lock. The inventory documents its read scope and the opt-in encoder-capability refresh behavior ([API_ROUTE_INVENTORY.md:33-37](../../inventories/API_ROUTE_INVENTORY.md)). The WebView fetches it with the current form values, rejects stale responses by request id, renders failures as unknown evidence, and labels backend start guards as final authority ([launchView.preflight.js:924-1006](../../apps/desktop/webview/static/assets/launchView.preflight.js)).

The preflight facade explicitly reports that the subsequent start route re-checks state ([preflight_facade.py:103-145](../../src/mediapipeline/core/processes/preflight_facade.py)). Tests cover read-only matching against launch guards, lock/schedule blocks, source validation, and optional capability-report refresh ([test_application_facade_process_launch.py:2000-2060](../../tests/python/desktop/test_application_facade_process_launch.py), [test_application_facade_process_launch.py:2654-2676](../../tests/python/desktop/test_application_facade_process_launch.py), [test_application_facade_process_launch.py:2233-2374](../../tests/python/desktop/test_application_facade_process_launch.py)).

### 3. Plan-only, dry-run, and execution semantics

Normal pipeline launch has four backend modes: `continuous`, `once`, `validate`, and `drain_pending_pushes` ([pipeline_policy.py:14-18](../../src/mediapipeline/core/processes/pipeline_policy.py)). Their PowerShell translation is explicit: `once` adds `-Once`, `validate` adds `-ValidateOnly`, and pending drain adds `-DrainPendingPushes` ([launch_plans.py:44-65](../../src/mediapipeline/core/processes/launch_plans.py)). The PowerShell entrypoint describes `-ValidateOnly` as dependency/startup checks that exit and `-EmitQueuePlan` as the actual queue-plan dry run ([MediaPipeline.ps1:15-24](../../ops/pipeline/entrypoints/MediaPipeline.ps1)).

CSV rerun is a separate Queue workflow: it has `plan_only` and `dry_run` launch-plan flags, which are mutually exclusive ([launch_plans.py:144-231](../../src/mediapipeline/core/processes/launch_plans.py)). It is not converted into `/api/pipeline/start`, as documented by the route inventory ([API_ROUTE_INVENTORY.md:342](../../inventories/API_ROUTE_INVENTORY.md)).

### 4. Start, pause, stop, and force-stop

The WebView posts start only to `/api/pipeline/start` ([launchView.js:1055-1114](../../apps/desktop/webview/static/assets/launchView.js)). It posts pipeline controls only to `/api/pipeline/control`; CSV rerun pause/stop is deliberately routed to its separate backend commands ([launchView.js:904-967](../../apps/desktop/webview/static/assets/launchView.js)).

The control facade validates the action, serializes controls with a non-blocking lock, writes backend-owned flags for pause/stop/rescan, and calls the backend service for kill ([control_facade.py:108-183](../../src/mediapipeline/core/processes/control_facade.py)). Kill also resets stuck progress after related-process cleanup, so it remains a high-impact backend action—not a frontend process operation ([control_facade.py:150-163](../../src/mediapipeline/core/processes/control_facade.py)).

### 5. Start locking, active work, restart, stale UI, and retry

Before spawn, the facade acquires the process launch lock and then re-checks active work ([pipeline_facade.py:103-124](../../src/mediapipeline/core/processes/pipeline_facade.py)). PowerShell adds an independent named global mutex for non-validate normal runs and explicitly protects pending drains with the same mutex ([MediaPipeline.ps1:316-349](../../ops/pipeline/entrypoints/MediaPipeline.ps1)). Tests prove the shared Python launch lock, a duplicate live-process rejection, stale-guard handling, and fresh stop-requested progress blocking ([test_application_facade_process_launch.py:1793-1823](../../tests/python/desktop/test_application_facade_process_launch.py), [test_application_facade_process_launch.py:1825-1884](../../tests/python/desktop/test_application_facade_process_launch.py)).

For stale UI, the Start button may remain enabled if cached preflight is absent or stale, but it describes that state and relies on the authoritative submission-time re-check ([commandButtons.js:66-91](../../apps/desktop/webview/static/assets/launch/commandButtons.js)). Successful starts trigger snapshot refreshes at 2/6/12 seconds ([launchView.js:1088-1095](../../apps/desktop/webview/static/assets/launchView.js)). Failed starts are rendered with the backend result and Launch history gives an explicit read-first Diagnostics/ActiveJobs/queue retry sequence ([launchHistoryView.js:233-239](../../apps/desktop/webview/static/assets/launchHistoryView.js), [launchHistoryView.js:457-484](../../apps/desktop/webview/static/assets/launchHistoryView.js)).

## Findings

### CSW-2026-07-09-LAUNCH-001 — P1: Empty pipeline-start payload defaults to live processing

**Evidence.** `PipelineStartCommandPayload` declares all fields optional, including `mode` ([api_commands.py:571-577](../../src/mediapipeline/contracts/api_commands.py)). The generic command boundary consequently accepts known route payloads without requiring a mode ([boundary.py:51-65](../../src/mediapipeline/core/validation/boundary.py)). `normalize_pipeline_start_mode()` converts a missing/falsey value to `"once"` ([pipeline_policy.py:54-55](../../src/mediapipeline/core/processes/pipeline_policy.py)); the facade accepts that supported mode and reaches `service.start_pipeline` ([pipeline_facade.py:76-84](../../src/mediapipeline/core/processes/pipeline_facade.py), [pipeline_facade.py:124-143](../../src/mediapipeline/core/processes/pipeline_facade.py)).

**Impact.** A valid-token request with `{}` is not rejected as missing launch intent; it becomes a live queue-processing run. The normal WebView defaults its select to `validate` ([startRequest.js:19-32](../../apps/desktop/webview/static/assets/launch/startRequest.js)), but that client-side default cannot protect API callers, tests, browser developer tools, or a stale shell. This contradicts the requested backend-owned strict request posture for a high-risk process-launch route.

**Smallest safe fix.** Make `mode` a required `Literal["once", "continuous", "validate", "drain_pending_pushes"]` in `PipelineStartCommandPayload`; reject absent/null/empty mode at both the route contract and `normalize_pipeline_launch_intent()`/facade boundary. Do not replace the missing mode with a live default. Retain the WebView’s explicit `validate` default.

**Required validation.** Add contract tests that `{}`, `{"mode": null}`, `{"mode": ""}`, and an invalid mode return HTTP 400/journaled validation evidence without calling `start_pipeline`; add facade-level defense-in-depth tests that no missing-mode request can invoke the service. Re-run the targeted command-contract, process-launch, local-API HTTP, and Launch browser smoke suites. A real-media run is not required for this request-contract fix.

### CSW-2026-07-09-LAUNCH-002 — P2: Pipeline-start controls are not typed strictly at the backend boundary

**Evidence.** The pipeline-start contract uses `Any` for `sleep_seconds`, `show_config`, `show_console`, `single_file`, and `schedule_override` ([api_commands.py:571-577](../../src/mediapipeline/contracts/api_commands.py)). The launch intent then coerces display flags with `bool(...)` and converts the schedule value with `str(...)` ([launch_intent.py:64-93](../../src/mediapipeline/core/processes/launch_intent.py)); sleep parsing truncates/coerces with `int(value or 30)` ([pipeline_policy.py:62-66](../../src/mediapipeline/core/processes/pipeline_policy.py)). The contract tests cover unknown extra fields and strict confirmations for other mutation routes, but the accepted `/api/pipeline/start` case checks only `mode` ([test_api_command_contracts.py:207-321](../../tests/python/desktop/test_api_command_contracts.py)).

**Impact.** Direct callers can submit unintended-but-accepted values—for example a non-empty string in `show_console`/`show_config` becomes true, and a fractional numeric sleep value is silently coerced. This is not a source-mutation bypass because the backend still owns scope, locks, source validation, and PowerShell launch; it is nevertheless a contract/observability defect on the launch route and makes the inventory’s allowed-value contract weaker than advertised.

**Smallest safe fix.** Use `StrictBool` for the display flags; a bounded `StrictInt` for sleep seconds; `StrictStr | None` for `single_file`; and a literal enum for `schedule_override` (`""`, `run_once`, `ignore`). Preserve the downstream validation as defense in depth rather than relying on coercion.

**Required validation.** Add parameterized API contract and HTTP tests for strings/numbers/booleans in each field, asserting 400 plus a journaled validation-failure entry and zero service starts. Cover accepted boundary values and verify the Launch browser smoke still posts correctly typed values. No real-media validation is required.

## Verified no-finding coverage

- **Frontend policy boundary:** `launchView.risk`, `launchView.scope`, `launchView.realmedia`, and `launch/risk/*` contain advisory rendering/data transformations rather than `apiPost`, filesystem, process, or FFmpeg calls. Their source repeatedly states policy is saved/backend-owned; the mutation-boundary test enforces advisory-only helpers ([test_webview_frontend_mutation_boundary.py:900-945](../../tests/webview/test_webview_frontend_mutation_boundary.py)).
- **Source/scratch safety:** direct single-file starts are source-root constrained before spawn; both route paths copy to scratch before media transforms. No reviewed Launch JavaScript writes source, scratch, output, or manifest files.
- **Duplicate start and in-progress controls:** frontend busy state is only a usability guard; Python lock plus active-work evidence plus the PowerShell mutex are the authoritative layers.
- **Command evidence:** handler success results are journaled; validation and route-exception failures are separately journaled for journaled routes ([handler.py:105-126](../../src/mediapipeline/desktop/api/handler.py), [handler.py:148-163](../../src/mediapipeline/desktop/api/handler.py), [handler_policy.py:92-124](../../src/mediapipeline/desktop/api/handler_policy.py)). The journal uses a bounded, atomic JSON save and SQLite mirror status ([command_journal.py:49-74](../../src/mediapipeline/desktop/api/command_journal.py), [command_journal.py:136-202](../../src/mediapipeline/desktop/api/command_journal.py)).
- **Failed preflight/retry behavior:** preflight failures render as unknown rather than start authorization; retry guidance directs diagnostics inspection before another start. Backend still rechecks state at submission.
- **Control scope:** pause/stop/rescan use flags; force-stop is backend-owned related-process cleanup. The WebView does not call a shell, PowerShell, or browser filesystem API.

## Test and contract assessment

Coverage is strong for launch locking, active work, schedule gates, preflight read-only behavior, source-root validation, encoder-capability evidence, frontend command ownership, and browser-level Launch rendering. The current contract suite is also strong for strict confirmation fields on routes that declare them.

The gap is specific: `/api/pipeline/start` does not make its intent and scalar types strict, and the existing tests do not assert rejection of missing/ill-typed start fields. The requested fixes should add the tests named in each finding before treating the route contract as strict.

No test command was run for this review. This was a static, read-only review under the instruction not to launch the pipeline, invoke a real launch, or invoke mutation routes.

## Cross-tab handoff

- **Queue:** Queue display/selection is advisory for normal pipeline start; Queue should continue to surface backend route/scope evidence without implying a selected row becomes `/api/pipeline/start` scope.
- **Settings:** Settings owns saved policy and strict save confirmation. Launch should consume only the saved backend workspace; staged settings remain non-active until backend save and reload.
- **Diagnostics/Home:** retry investigation should begin with command result, ActiveJobs, run logs/last stderr, and queue snapshot. Command Journal persistence degradation should stay visible to these tabs.
- **Pending Publish/Completed:** `drain_pending_pushes` is a backend pipeline mode; final placement, parked-output state, and successful drain proof remain owned by Pending Publish and Completed, not Launch.
- **Tauri:** close readiness remains a backend response; the shell must not infer safety from Launch UI state.

## Review limits

Reviewed the specified Launch partial/view/modules, launch history/readiness, route contracts/handlers, process facades/services, PowerShell entry and process/publish handoffs, route/ownership inventories, and relevant Python/WebView/PowerShell tests. Generated summaries were consulted before source where present; several generated WebView summaries are explicitly unparsed and supplied no behavioral detail.

This review did not run a Local API, a browser smoke, PowerShell, FFmpeg, a real-media pilot, or any mutation route. It therefore verifies static ownership and contract paths, not runtime media behavior, environmental tool availability, process termination timing, or finished-output playback.
