# Worker Review: worker-01-backend-api-application

## Scope

Worker ID: `worker-01-backend-api-application`

Assigned W01 scope from `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`: 143 Python files covering backend API/application surfaces: `src/mediapipeline/core/api/`, `src/mediapipeline/desktop/api/`, desktop application DTO/facade/adapters, local API startup, and desktop network HTTP coordinator/worker surfaces.

Review focus: route correctness, command journaling, duplicate-command safety, backend ownership, close-readiness, API error handling, DTO/contract drift, unsafe mutation exposure, and route test gaps.

Coverage status: partial. Local API route/command/contract/strict JSON surfaces received targeted source review and read-only probes. The full W01 file list was inventoried from the assignment table and searched for safety patterns, but not every function in all 143 files was fully source-reviewed.

## Coverage Ledger

Required context read:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`

Summary-first checks:

- Checked generated summaries under `docs/generated/summaries/src/mediapipeline/core/api/`, `docs/generated/summaries/src/mediapipeline/desktop/api/`, `docs/generated/summaries/src/mediapipeline/desktop/application/`, `docs/generated/summaries/src/mediapipeline/desktop/network/`, and adjacent DTO/facade summaries before opening source.
- W01 assignment rows all show `Summary exists: yes`.
- No W01 summary inspected reported `token_priority: high`; implementation source was opened where summaries did not include enough behavior for route parsing, command dispatch, journaling, auth, and strict JSON review.

Targeted full-source review:

- Local API host/routing: `src/mediapipeline/desktop/api/handler.py`, `http_helpers.py`, `handler_policy.py`, `routes.py`, `routes_command.py`, `routes_read.py`, `routes_shared.py`, `server.py`, `static_files.py`, `static_files_policy.py`, `local_api_main.py`.
- Command registry/results/journal: `src/mediapipeline/core/api/commands.py`, `command_handlers.py`, `command_results.py`, `src/mediapipeline/desktop/api/command_journal.py`, `command_journal_policy.py`.
- Command handler samples covering mutation boundaries: `commands_process.py`, `commands_rename.py`, `commands_settings.py`, `commands_queue_priority.py`, `commands_queue_strategy.py`, `commands_files.py`, `commands_failures.py`, `commands_audit.py`, `commands_maintenance.py`, `commands_final_library.py`, `commands_sample_validation.py`, `commands_schedule.py`, `commands_ui_preferences.py`.
- Route contracts: `src/mediapipeline/desktop/api/contract.py`, `contract_command.py`, `contract_read.py`, `contract_payload.py`, `contract_shared.py`, plus generated API validation boundary as supporting evidence.
- DTO/application boundary: `src/mediapipeline/desktop/application/dto.py`, `dto_base.py`, `dto_commands.py`, `facade.py`, and supporting `src/mediapipeline/core/kernel/dto_base.py`, `dto_commands.py`.
- Network HTTP/auth strictness: `src/mediapipeline/desktop/network/json_policy.py`, `http_json.py`, `auth.py`, `coordinator_http.py`, `coordinator_auth.py`, `coordinator_http_handlers.py`, `coordinator_parts/http_server.py`, `worker_http.py`.
- Sample validation facade checked for return-shape consistency: `src/mediapipeline/core/sample_validation/facade.py`.

Read-only probes run:

- Route contract drift:
  - Command routes: 58 registered, 58 documented; missing `[]`, extra `[]`.
  - Read routes plus `/api/health`: 45 registered/public, 45 documented; missing `[]`, extra `[]`.
- AST command handler coverage:
  - Every `COMMAND_ROUTE_METHODS` method name was found in command handler mixin source.
- Strict/high-risk payload validation spot checks:
  - `/api/backend/shutdown` and `/api/rename/apply` reject unexpected fields.
  - Compatibility route `/api/queue/priority` still accepts unexpected fields by generated-contract design.
- Targeted fresh-process imports:
  - Failing: `mediapipeline.core.api.command_handlers`, `mediapipeline.core.api.commands_process`, `mediapipeline.core.api.commands_rename`, `mediapipeline.core.api.commands_settings`.
  - Passing: `mediapipeline.desktop.api.server`, `mediapipeline.desktop.api.handler`, `mediapipeline.desktop.api.path_dialogs`, `mediapipeline.desktop.api.contract_payload`, `mediapipeline.desktop.application.facade`, `mediapipeline.desktop.local_api_main`, `mediapipeline.desktop.network.coordinator_parts.http_server`, `mediapipeline.desktop.network.coordinator_http_handlers`, `mediapipeline.desktop.network.worker_http`.
- Safety-pattern search over W01 source for direct `os.replace`, `unlink`, `rename`, `shutil`, `subprocess`, `kill`, `write_text`, `mkdir`, `save`, `apply`, `promote`, `drain`, `delete`, and `move`.

## Findings Summary

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 0 |

## Detailed Findings

### Medium: Direct imports of core API command modules fail because command modules import `desktop.api.path_dialogs` through a package that imports the server

Files:

- `src/mediapipeline/core/api/command_handlers.py`
- `src/mediapipeline/core/api/commands_process.py`
- `src/mediapipeline/core/api/commands_rename.py`
- `src/mediapipeline/core/api/commands_settings.py`
- `src/mediapipeline/desktop/api/__init__.py`
- `src/mediapipeline/desktop/api/server.py`

Symbol/section:

- `LocalApiCommandHandlerMixin`
- `LocalApiProcessCommandPayloadMixin`
- `LocalApiRenameCommandPayloadMixin`
- `LocalApiSettingsCommandPayloadMixin`
- `desktop.api` package exports

Evidence:

- `command_handlers.py:10` imports `LocalApiProcessCommandPayloadMixin`.
- `commands_process.py:7`, `commands_rename.py:5`, and `commands_settings.py:6` import `select_windows_paths_with_dialog` from `mediapipeline.desktop.api.path_dialogs`.
- Importing that submodule initializes `mediapipeline.desktop.api.__init__`; `desktop/api/__init__.py:4` imports `LocalApiServer`.
- `desktop/api/server.py:14` imports `LocalApiCommandHandlerMixin`, re-entering the partially initialized core command module.
- Fresh-process probes reproduced the failures:
  - `python -c "from mediapipeline.core.api.command_handlers import LocalApiCommandHandlerMixin"` fails with `ImportError: cannot import name 'LocalApiCommandHandlerMixin' from partially initialized module`.
  - `python -c "import mediapipeline.core.api.commands_process"` fails with the same circular import pattern.
  - `python -c "import mediapipeline.core.api.commands_rename"` fails because `LocalApiRenameCommandPayloadMixin` is partially initialized.
  - `python -c "import mediapipeline.core.api.commands_settings"` fails because `LocalApiSettingsCommandPayloadMixin` is partially initialized.
- Normal desktop startup import paths still passed in targeted checks: `mediapipeline.desktop.api.server`, `mediapipeline.desktop.api`, and `mediapipeline.desktop.local_api_main` imported successfully.

Impact:

The canonical core API command modules are import-order dependent. Tooling, tests, alternate API hosts, or future refactors that import `mediapipeline.core.api.command_handlers` or one of the affected command modules directly can fail before any route tests run. This also weakens the intended core/desktop boundary because `src/mediapipeline/core/api/` reaches into the `desktop.api` package for a UI dialog helper, and that package eagerly imports the local API server.

Fix direction:

Move or isolate the Windows path dialog helper so core API command modules do not import through `mediapipeline.desktop.api.__init__`. Acceptable directions include moving the helper to a neutral desktop adapter module that does not import the server, making the dialog import lazy inside the browse handlers, or making `desktop/api/__init__.py` stop eagerly importing `LocalApiServer`. Add fresh-process import tests for `mediapipeline.core.api.command_handlers`, `commands_process`, `commands_rename`, and `commands_settings`.

Validation:

- Reproduce before fix with fresh-process imports listed above.
- After fix, run those imports plus existing focused API tests:
  - `apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_application_facade_core_contracts tests.python.desktop.test_api_command_contracts tests.python.desktop.test_application_facade_local_api -q`
  - Relevant Local API smoke wrapper if the implementation changes startup/import behavior.

## Test Coverage Gaps

- No focused test currently asserts fresh-process importability of `mediapipeline.core.api.command_handlers` and affected core command modules before `mediapipeline.desktop.api` is imported.
- The full W01 isolated import sweep timed out before completion in this review session; targeted fresh-process imports were used instead.
- Compatibility command models intentionally allow unknown fields on some lower-risk routes. High-risk route strictness is covered, but future route additions should explicitly decide `extra="forbid"` versus compatibility allowance.
- I did not run a live Local API server or smoke wrapper because this was review-only and no runtime/media state should be mutated. Existing test inventory shows focused Local API lifecycle, command journal, strict JSON, network HTTP, and route contract tests.

## Boundary Risks

- The confirmed circular import is also a boundary smell: core API modules import `mediapipeline.desktop.api.path_dialogs`, and the `desktop.api` package imports the server. This couples core command assembly to desktop package initialization.
- Local API route code reviewed here does not directly implement media mutation policy. Mutation-capable routes delegate to backend facade/service methods, and route contracts for rename apply, pipeline start/control, settings save, schedule save, final-library promotion, and maintenance operations are strict for unknown fields.
- Network coordinator/worker modules intentionally mutate coordinator in-flight state, worker state, and cluster logs. Reviewed HTTP/auth/JSON paths keep those writes backend-owned and non-daemon request handlers are configured where claim/done/log cleanup matters. This review did not fully audit every worker runtime function.
- Command journal persistence is best-effort: save failures are logged rather than blocking command success. Existing tests assert this policy; changing it would be a behavior decision beyond this review.

## Files Reviewed With No Findings

Full-source reviewed with no additional findings:

- `src/mediapipeline/core/api/command_results.py`
- `src/mediapipeline/core/api/commands.py`
- `src/mediapipeline/core/api/commands_audit.py`
- `src/mediapipeline/core/api/commands_failures.py`
- `src/mediapipeline/core/api/commands_files.py`
- `src/mediapipeline/core/api/commands_final_library.py`
- `src/mediapipeline/core/api/commands_maintenance.py`
- `src/mediapipeline/core/api/commands_queue_priority.py`
- `src/mediapipeline/core/api/commands_queue_strategy.py`
- `src/mediapipeline/core/api/commands_sample_validation.py`
- `src/mediapipeline/core/api/commands_schedule.py`
- `src/mediapipeline/core/api/commands_ui_preferences.py`
- `src/mediapipeline/desktop/api/command_journal.py`
- `src/mediapipeline/desktop/api/command_journal_policy.py`
- `src/mediapipeline/desktop/api/contract.py`
- `src/mediapipeline/desktop/api/contract_command.py`
- `src/mediapipeline/desktop/api/contract_payload.py`
- `src/mediapipeline/desktop/api/contract_read.py`
- `src/mediapipeline/desktop/api/contract_shared.py`
- `src/mediapipeline/desktop/api/handler.py`
- `src/mediapipeline/desktop/api/handler_policy.py`
- `src/mediapipeline/desktop/api/http_helpers.py`
- `src/mediapipeline/desktop/api/path_dialogs.py`
- `src/mediapipeline/desktop/api/routes.py`
- `src/mediapipeline/desktop/api/routes_command.py`
- `src/mediapipeline/desktop/api/routes_read.py`
- `src/mediapipeline/desktop/api/routes_shared.py`
- `src/mediapipeline/desktop/api/server.py`
- `src/mediapipeline/desktop/api/static_files.py`
- `src/mediapipeline/desktop/api/static_files_policy.py`
- `src/mediapipeline/desktop/application/dto.py`
- `src/mediapipeline/desktop/application/dto_base.py`
- `src/mediapipeline/desktop/application/dto_commands.py`
- `src/mediapipeline/desktop/application/facade.py`
- `src/mediapipeline/desktop/local_api_main.py`
- `src/mediapipeline/desktop/network/auth.py`
- `src/mediapipeline/desktop/network/coordinator_auth.py`
- `src/mediapipeline/desktop/network/coordinator_http.py`
- `src/mediapipeline/desktop/network/coordinator_http_handlers.py`
- `src/mediapipeline/desktop/network/coordinator_parts/http_server.py`
- `src/mediapipeline/desktop/network/http_json.py`
- `src/mediapipeline/desktop/network/json_policy.py`
- `src/mediapipeline/desktop/network/worker_http.py`

Summary/static-search reviewed with no findings raised in this pass:

- Remaining W01 desktop application sample-validation helpers.
- Remaining W01 desktop contracts/model compatibility files.
- Remaining W01 desktop network coordinator/worker support modules.
- Remaining W01 file-overrides helper modules, except for command registry/route coverage checks.

## Files Marked Out Of Scope

- `src/mediapipeline/core/api/commands_metrics.py` and `src/mediapipeline/core/api/commands_subtitle_qa.py`: present in `src/mediapipeline/core/api/` and included in command handler/route-method AST checks, but not listed in W01 assignment rows. They were not full-source reviewed.
- `src/mediapipeline/core/kernel/*`: adjacent DTO implementation behind desktop compatibility shims. Only `dto_base.py` and `dto_commands.py` were consulted to confirm `CommandResult` serialization.
- `tests/**`: consulted for coverage evidence only, not reviewed as part of W01.
- Existing `docs/reviews/function-module-audit-2026-06-11/workers/W01-backend-api-application.md`: not touched; requested output path is `worker-01-backend-api-application.md`.

## Incomplete Coverage

- Partial coverage overall. The highest-risk Local API route/command/contract/strict JSON surfaces were reviewed, but not every function in all 143 assigned W01 files was manually source-reviewed.
- The full isolated import sweep across all W01 modules timed out after about 125 seconds. Targeted fresh-process imports found the confirmed circular import defect and verified several primary runtime imports.
- No live API startup, browser, Tauri, or real-media validation was run because this report is review-only and no source/media/runtime mutation was requested.
- Final change-control validation failed because unrelated `docs/implementation/encoder-breadth-av1-plan.md` is not listed in any unreleased packet. This worker packet covers its two touched files.
