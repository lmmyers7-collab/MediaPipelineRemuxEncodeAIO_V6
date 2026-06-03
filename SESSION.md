# SESSION.md — Current session scope

Created: 2026-06-02
Branch: master
Operator-approved scope (chat, 2026-06-02): execute ADR-0013 Wave 1 step 1,
Wave 2 (steps 2-3), Wave 3 (steps 4-5), Wave 4 (step 6), then Wave 5
(steps 7-8) on follow-up approval ("just continue").

## Config hardening #1 2026-06-02 (AGENTS.md §7; operator-approved this turn)

Task: startup self-heal for the live config so it cannot silently go missing.
Spans app/ + DesktopApp/ (operator approved "create the plan then perform it").

In-scope:
- NEW `app/config/recovery.py` -- `ensure_canonical_config(app_root,
  workspace_root)`: present / migrated (legacy _chatgpt -> canonical copy) /
  backup_available (names newest ConfigBackups entry) / absent. Filesystem
  only (no PowerShell), unit-testable.
- EDIT `DesktopApp/mediapipeline_desktop_app/local_api_main.py` build_backend:
  call recovery before default_config_path(); add startup steps for the
  recovery outcome and a verify_config_loaded signal from resolved.config_data.
- NEW `DesktopApp/tests/test_config_recovery.py`.

NOT self-certified (§7): operator restart + pending-publish smokes required.
No parsing/saving/publish behaviour changed; only config presence + startup
reporting.

Status 2026-06-02: implemented. Changed files:
- `app/config/recovery.py` (new) -- ensure_canonical_config + ConfigRecoveryResult.
- `DesktopApp/mediapipeline_desktop_app/local_api_main.py` -- import; build_backend
  now runs recovery before default_config_path() (only when no explicit
  --config-path) and adds `recover_config` + `verify_config_loaded` startup steps.
- `DesktopApp/tests/test_config_recovery.py` (new) -- 5 unit tests.

Validation (agent-side): compileall clean; recovery unit tests 5/5;
startup/facade tests 66 passed; full suite 1641 passed, 1 skipped, 1235
subtests, exit 0. End-to-end (runtime-sim) against the real layout:
recovery=present, startup steps recover_config=complete,
verify_config_loaded="settings loaded".

Operator validation REQUIRED before §7 sign-off:
- `.\scripts\dev\start-local-api.bat` then confirm startup JSON shows
  `recover_config` and `verify_config_loaded` complete.
- `SmokeTests\Test-WebViewBrowserPendingDrainGuardSmoke.ps1` and
  `SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1` (confirm no regression;
  this change does not touch publish/queue).
- `python scripts\dev\ai_guardrail.py`.

## Red-baseline cleanup 2026-06-03 (operator-approved; separate from kernel migration)

Wave-6 prerequisite: 8 failing tests caused by incomplete rename/settings
WebView work (live code added GET routes /api/rename/clean-filename-preview &
/api/rename/movie-cleaning-filters + new settings DOM/export functions) with
stale hand-maintained docs. NOT the kernel migration. Operator approved
fixing as a scoped doc-sync task.

In-scope (sync docs to live code only; no behaviour change):
- Docs/inventories/API_ROUTE_INVENTORY.md
- Docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md
- evidence-mutation matrix doc (per test_api_route_inventory)
- tauri required-routes list (DesktopApp/tauri_shell scaffold)
- SmokeTests/Test-WebViewBrowserMaintenanceReportsSmoke.ps1 (add phrase)
- Docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md
- Docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md
New GET routes classified read/non-mutating; route-governance classifications
flagged for operator review.

## Config hardening #1b 2026-06-02 -- per-user config location (Tauri packaged)

Operator-approved (AskUserQuestion): packaged Tauri build can't find the
gitignored personal config because it's not bundled. Fix: resolve a per-user
location `%LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO\MediaPipeline_config.psd1`
as a fallback for both dev and packaged.

In-scope:
- `app/paths/defaults.py` -- add user_config_dir()/user_config_candidates()
  (LOCALAPPDATA-based; [] if unset). Pure resolver default_config_path_for_roots
  left UNCHANGED (test stability).
- `app/paths/service.py` -- default_config_path(): local-if-exists else
  per-user-if-exists else local default.
- `app/config/recovery.py` -- per-user self-heal branch + seed_user_config().
- `DesktopApp/tests/test_config_recovery.py` -- per-user tests with controlled
  LOCALAPPDATA.
- Seed: copy current Pipeline/MediaPipeline_config.psd1 -> per-user location.

NOT self-certified (§7 + Tauri lifecycle): operator must run a packaged Tauri
launch to confirm the backend now resolves the per-user psd1. No Rust/shell
change needed (backend already passes --app-root and no --config-path).

Status 2026-06-02: implemented. Design note: per-user selection lives at the
startup boundary (build_backend uses recovery.canonical_path), NOT in
service.default_config_path() -- putting it in the pervasive method caused
order-dependent failures (temp-root tests resolving the real per-user file).
service.default_config_path() and default_config_path_for_roots stay pure.

Changed files:
- `app/paths/defaults.py` -- user_config_dir()/user_config_candidates() +
  CONFIG_CANONICAL_NAME/CONFIG_LEGACY_NAME/PER_USER_APP_DIR_NAME constants.
- `app/config/recovery.py` -- imports names from defaults; per-user branch
  (user_present / user_migrated); seed_user_config().
- `DesktopApp/mediapipeline_desktop_app/local_api_main.py` -- build_backend
  selects recovery.canonical_path when no explicit --config-path.
- `DesktopApp/tests/test_config_recovery.py` -- per-user + seed tests with
  controlled LOCALAPPDATA (13 tests).
- Seeded: copied Pipeline/MediaPipeline_config.psd1 ->
  %LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO\MediaPipeline_config.psd1 (19991 B).

Validation (agent-side): compile clean; recovery+path tests 15/15 then full
recovery 13/13; full suite 1648 passed, 1 skipped, 1235 subtests, exit 0.
End-to-end: DEV resolves local repo config (present); PACKAGED-sim resolves
the real per-user config (user_present).

Operator validation REQUIRED (§7/Tauri): launch the packaged Tauri build and
confirm startup shows recover_config=complete (user_present) and
verify_config_loaded="settings loaded"; pending-publish + local-API contract
smokes for regression.

## Packaged Tauri "settings not loading" 2026-06-02 -- root cause + rebuild

Symptom: packaged Tauri build showed defaults / "settings loaded=no".
Root cause (proven): the running app was a STALE package from 2026-05-29
(`%TEMP%\MediaPipelineRemuxEncodeAIO_V6_Deployable_Codex_20260529_*`). Its
bundled Python predates the recovery/per-user fix (no recovery.py, no
user_config_dir, no recover_config step) AND it shipped with only
`MediaPipeline_config_template.psd1` (no live config). Its old resolver
pointed at a non-existent `_chatgpt` path -> config never loaded. The
per-user fix/seed cannot help that bundle because its code never checks
per-user. No package newer than 05-29 existed; "rebuilt" was not in effect.

Resolution: rebuilt from current source via `scripts\release\build.ps1`
(invoked directly, NOT with -ExecutionPolicy Bypass which the harness blocks).
First build (`..._Deployable_20260602_152939`, default mode "live config
stripped") contains the fix; its backend, run as the Tauri shell would
(`-m mediapipeline_desktop_app.local_api_main --app-root <pkg>\DesktopApp
--shell-surface tauri --emit-startup-progress`), resolved
`%LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO\MediaPipeline_config.psd1` with
recover_config=complete and verify_config_loaded=complete (settings loaded),
no errors. That default build omitted the standalone shell exe
(-IncludeTauriPreviewBinary is opt-in), so a second build was run WITH that
flag to produce a launchable package.

Operator: launch the NEWEST `..._Deployable_2026*` package; confirm in GUI
(Video tab VideoQuality=21 not 22; Libraries shows Movies/TV with
\\LAYNE-SERVER paths). The 05-29 Temp packages are stale and can be deleted.

## Operator config fix 2026-06-02 (separate from kernel migration)

Operator reported "settings lost" / pipeline blocked ("settings loaded=no").
Diagnosis: data was NOT lost. Canonical V7 live config
`Pipeline/MediaPipeline_config.psd1` did not exist; resolver fell back to the
legacy `Pipeline/MediaPipeline_config_chatgpt.psd1` (intact, newest, loads).
The documented `_chatgpt` -> canonical rename (see `app/paths/defaults.py`
comment) was never completed.

Action (non-destructive, both files gitignored): copied the intact
`MediaPipeline_config_chatgpt.psd1` -> `MediaPipeline_config.psd1`. Verified:
byte-identical; canonical now resolves as active config and `load_config`
validates; real settings present (SourceMovies/SourceTV/Outsource
`\\LAYNE-SERVER\...`, movies+tv library profiles). `_chatgpt` left in place
as fallback. No code changed. Operator must restart local API + hard-refresh
browser to pick it up.

## Wave 5 in-scope files (added 2026-06-02) -- AGENTS.md §7 (pending_publish)

Move whole package `DesktopApp/mediapipeline_desktop_app/contracts/`
-> `app/kernel/contracts/` (all 10 modules: __init__, base, active_job,
completed_job, control_flag, pending_publish, pipeline_events,
process_result, progress, queue_snapshot). Package is self-contained (every
module imports only `from .base ...`).

Recreate old `contracts/` as a shim package (robust re-export shims for each
module; __init__ shim preserves the aggregator `__all__`).

NOT self-certified: `pending_publish` is §7 release-critical. Agent-side
tests run, but operator high-risk rung + sign-off required before this wave
is "done" (see handoff).

## Wave 4 in-scope files (added 2026-06-02)

Create (move from DesktopApp `application/`):
- `app/kernel/dto_status.py`
- `app/kernel/dto.py`        (aggregator; imports the five moved siblings)

Replace with robust compatibility shims (full namespace + literal __all__):
- `DesktopApp/mediapipeline_desktop_app/application/dto_status.py`
- `DesktopApp/mediapipeline_desktop_app/application/dto.py`

## Wave 3 in-scope files (added 2026-06-02)

Create (move from DesktopApp `application/`):
- `app/kernel/dto_base.py`
- `app/kernel/dto_commands.py`
- `app/kernel/dto_inventory.py`
- `app/kernel/dto_workspaces.py`

Replace with robust compatibility shims (re-export full public namespace,
including non-`__all__` names like `JsonMap`):
- `DesktopApp/mediapipeline_desktop_app/application/dto_base.py`
- `DesktopApp/mediapipeline_desktop_app/application/dto_commands.py`
- `DesktopApp/mediapipeline_desktop_app/application/dto_inventory.py`
- `DesktopApp/mediapipeline_desktop_app/application/dto_workspaces.py`

## Wave 2 in-scope files (added 2026-06-02)

Create:
- `app/kernel/config_keys.py`              (moved from DesktopApp)
- `app/kernel/runtime/__init__.py`
- `app/kernel/runtime/subprocess_runner.py`(moved from DesktopApp)

Replace with compatibility shims:
- `DesktopApp/mediapipeline_desktop_app/config_keys.py`
- `DesktopApp/mediapipeline_desktop_app/subprocess_runner.py`

## Task

Shared-kernel extraction, Wave 1 step 1 (ADR-0012, ADR-0013): relocate the
`models` trio to the new `app/kernel/` package behind re-export shims. No
importer rewrites this session (deferred to ADR-0013 Wave 6).

## In-scope files

Create:
- `app/kernel/__init__.py`
- `app/kernel/models.py`            (moved from DesktopApp)
- `app/kernel/models_core.py`       (moved from DesktopApp)
- `app/kernel/models_media_paths.py`(moved from DesktopApp)

Replace with compatibility shims (old paths re-export from `app.kernel.*`):
- `DesktopApp/mediapipeline_desktop_app/models.py`
- `DesktopApp/mediapipeline_desktop_app/models_core.py`
- `DesktopApp/mediapipeline_desktop_app/models_media_paths.py`

Docs already updated this session: `Docs/adr/0012-*`, `Docs/adr/0013-*`,
`Docs/adr/README.md`.

## Out of scope

- Rewriting the 92/5/1 importers (Wave 6).
- Any other kernel member (config_keys, subprocess_runner, dto_*, contracts).
- Any behaviour change. This is a pure relocation.

## High-risk note (AGENTS.md §7)

`models.py` defines `QueueRecord` (queue types). The change is type-only
relocation, but the queue/settings validation rung applies and is for the
operator to run; this session does not self-certify §7.

## Validation rung (AGENTS.md §5)

- Agent-side: full Python unit suite via `DesktopApp\Runtime\Python\python.exe`.
- Operator-side (required before declaring §7-safe): queue/settings targeted
  tests + affected smokes; representative real-media validation if any queue
  behaviour is suspected to change (it should not).

## Exit criteria

- `app.kernel.models`, `app.kernel.models_core`, `app.kernel.models_media_paths`
  import successfully.
- Old import paths still resolve via shims.
- Python unit suite green (or pre-existing failures identified as unrelated).
- Handoff recorded below.

## Handoff 2026-06-02

Status: Wave 1 step 1 complete; exit criteria met (agent-side). Operator §7
validation still required (see below).

Changed files:
- `app/kernel/__init__.py` (new) — kernel package marker/docstring.
- `app/kernel/models.py`, `app/kernel/models_core.py`,
  `app/kernel/models_media_paths.py` (new home; `git mv` from DesktopApp,
  history preserved). No content edits; `models.py` relative imports of the
  other two still resolve in-package.
- `DesktopApp/mediapipeline_desktop_app/models.py`, `models_core.py`,
  `models_media_paths.py` (now compatibility shims: `from app.kernel.X import *`).
- `Docs/adr/0012-*`, `Docs/adr/0013-*`, `Docs/adr/README.md` (the two ADRs +
  index; 0013 corrected to `app/kernel/` and shim-defers-rewrite).

Validation performed (agent-side):
- Import smoke: new paths + shims import; `mediapipeline_desktop_app.models.QueueRecord`
  is the identical object as `app.kernel.models.QueueRecord`.
- `compileall` clean on new + shim files.
- `pytest --collect-only` over `DesktopApp/tests`: 1630 collected, exit 0
  (no import breakage anywhere).
- `pytest` on the 59 files importing the moved modules: 464 passed, 46
  subtests passed, exit 0 (53s).
- Command env: `PYTHONPATH=<root>;<root>/DesktopApp`, interpreter
  `DesktopApp\Runtime\Python\python.exe`.

Operator validation still required (AGENTS.md §7, not self-certified):
- Queue/settings targeted smokes for `QueueRecord` relocation.
- `scripts/dev/ai_guardrail.py` (godfile/drift) to confirm the change
  reduces the `models` godfile and trips no guard.
- `python scripts/dev/refresh_summaries.py` — summaries still sit at the old
  `summaries/DesktopApp/.../models*.py.md` paths; regen to mirror
  `app/kernel/`. Not run this session to avoid a broad out-of-scope diff.

Not mine / pre-existing working-tree changes (left untouched): `renameView.js`,
`settingsView.js`, `test_rename_workbench_v7.py`,
`test_webview_settings_libraries.py`, and their summaries.

## Handoff 2026-06-02 (Wave 2)

Status: Wave 2 (steps 2-3) complete; exit criteria met (agent-side).
Operator §7 validation still required (config_keys feeds settings schema).

Changed files:
- `app/kernel/config_keys.py` (new home; `git mv`, no edits). Module-level
  `__all__` is computed from `globals()` and resolves correctly in the new
  location (134 `KEY_*` constants).
- `app/kernel/runtime/__init__.py` (new) — kernel runtime subpackage marker.
- `app/kernel/runtime/subprocess_runner.py` (new home; `git mv`, no edits).
- `DesktopApp/mediapipeline_desktop_app/config_keys.py`,
  `subprocess_runner.py` (now compatibility shims).

Validation performed (agent-side):
- `compileall` clean on new + shim files.
- Import smoke: shim re-exports identical `KEY_*` values; `subprocess_runner`
  public API (`CapturedCommandResult`, `KillTreeCallback`, ...) intact.
- `pytest --collect-only` over `DesktopApp/tests`: 1630 collected, exit 0.
- `pytest` on the 17 `.py` files importing the moved modules: 192 passed,
  140 subtests passed, exit 0.

Operator validation still required (AGENTS.md §7, not self-certified):
- Settings schema/persistence smokes (config_keys underpins settings keys).
- `scripts/dev/ai_guardrail.py`; `python scripts/dev/refresh_summaries.py`.

## Handoff 2026-06-02 (Wave 3)

Status: Wave 3 (steps 4-5) complete; exit criteria met (agent-side),
verified against the full suite.

Changed files:
- `app/kernel/dto_base.py`, `app/kernel/dto_commands.py`,
  `app/kernel/dto_inventory.py`, `app/kernel/dto_workspaces.py` (new home;
  `git mv`, no content edits; sibling `from .dto_base import ...` resolves
  in-package).
- `DesktopApp/mediapipeline_desktop_app/application/dto_base.py`,
  `dto_commands.py`, `dto_inventory.py`, `dto_workspaces.py` (robust shims:
  copy full public namespace via globals().update for back-compat, e.g.
  `JsonMap` which is not in `__all__`; plus a literal `__all__`).

Contract note (caught by test, then fixed):
- `tests/test_application_public_api.py` AST-parses every `application/dto*.py`
  and requires a literal-list `__all__`. Plain `import *` shims failed it;
  the robust shims now declare a literal `__all__` mirroring each moved
  module. This is why Wave 3 shims differ from the Wave 1-2 plain `import *`
  shims.

Validation performed (agent-side):
- `compileall` clean on new + shim files.
- Import smoke: `JsonMap`, `dto_mapping`, `json_safe` import via the shim;
  `dto_mapping` identity matches the kernel module; `dto.py`'s relative
  `from .dto_base import JsonMap` resolves via the shim.
- `pytest --collect-only` over `DesktopApp/tests`: exit 0.
- Full suite `pytest DesktopApp/tests`: 1631 passed, 1 skipped, 1235
  subtests passed, exit 0 (152s).

Operator validation still recommended: `scripts/dev/ai_guardrail.py`;
`python scripts/dev/refresh_summaries.py` (summaries still at old paths for
all moved modules across Waves 1-3).

## Handoff 2026-06-02 (Wave 4)

Status: Wave 4 (step 6) complete; exit criteria met, verified against the
full suite. DTO family fully relocated to the kernel.

Changed files:
- `app/kernel/dto_status.py`, `app/kernel/dto.py` (new home; `git mv`, no
  content edits). `dto.py` aggregator's `from .dto_* import ...` all resolve
  in-package now that every sibling lives in `app.kernel`.
- `DesktopApp/mediapipeline_desktop_app/application/dto_status.py`,
  `application/dto.py` (robust shims: full-namespace copy + literal `__all__`).

Validation performed (agent-side):
- `compileall` clean on new + shim files.
- Import smoke: `mediapipeline_desktop_app.application` still exposes
  `CommandResult` (via `__init__` -> `.dto` shim -> `app.kernel.dto`);
  aggregator object identity matches `app.kernel.dto`.
- Full suite `pytest DesktopApp/tests`: 1631 passed, 1 skipped, 1235
  subtests passed, exit 0 (146s).

Operator validation still recommended: `scripts/dev/ai_guardrail.py`;
`python scripts/dev/refresh_summaries.py` (summaries still at old paths for
all moved modules, Waves 1-4).

## Handoff 2026-06-02 (Wave 5) -- AGENTS.md §7, NOT self-certified

Status: mechanical move complete; agent-side tests green. NOT declared done
-- `pending_publish` is §7 release-critical; operator high-risk rung +
sign-off required (below).

Changed files:
- Whole package moved: `app/kernel/contracts/` now holds __init__, base,
  active_job, completed_job, control_flag, pending_publish, pipeline_events,
  process_result, progress, queue_snapshot (`git mv`, no content edits;
  package is self-contained, every module imports only `from .base ...`).
- `DesktopApp/mediapipeline_desktop_app/contracts/` recreated as a shim
  package: 9 submodule robust shims + an `__init__` shim that preserves the
  aggregator `__all__` (16 names).

Validation performed (agent-side only):
- `compileall` clean on the new package and the shim package.
- Import smoke: `PendingPushManifest`, `ContractError`, `QueuePlanSnapshot`
  resolve via shim with identical object identity to `app.kernel.contracts.*`;
  aggregator `__all__` count = 16; base helpers (`text_field`) callable via
  shim.
- Full suite `pytest DesktopApp/tests`: 1634 passed, 1 skipped, 1235
  subtests passed, exit 0 (147s).

Operator validation REQUIRED before Wave 5 is "done" (AGENTS.md §5/§7):
- `SmokeTests\Test-WebViewBrowserPendingDrainGuardSmoke.ps1`
- `SmokeTests\Test-WebViewBrowserCompletedPendingProofSmoke.ps1`
- `SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1`
- `python scripts\dev\ai_guardrail.py` (godfile/drift; expect `models`/
  contracts godfile pressure reduced, no new guard trips)
- Representative real-media validation per
  `scripts\operator\New-RealMediaValidationWorksheet.ps1` only if any
  publish/drain behaviour is suspected to change. This wave is a pure
  contract-type relocation; no behaviour change is intended.

Also recommended (all waves): `python scripts\dev\refresh_summaries.py`
(summaries still at old paths for every moved module, Waves 1-5).

Next step (new session): Wave 6 cleanup -- rewrite importers to the
`app.kernel.*` paths and delete all shims, then add the dependency-direction
check from ADR-0012 §Validation. Hold until ADR-0012/0013 are accepted and
the §7 validation above passes.

## Handoff 2026-06-03 -- MediaPipeline.ps1 keystone hardening (operator-approved in chat; separate from kernel migration)

Operator approved a code-review of the main pipeline file and, after a written
per-issue plan, said "I'll proceed with your suggestions" -- explicit
current-turn scope for `Pipeline/MediaPipeline.ps1` and
`Pipeline/MediaPipeline/remux.ps1`. NOT the ADR-0013 kernel work. Branch:
`fix/mediapipeline-keystone-hardening` (off `master`). Eight isolated commits,
end-to-end smoke (`Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1`) green after
each cut.

Changed files / commits (most severe first):
- `Pipeline/MediaPipeline.ps1` -- config-loader reserved-name denylist +
  try/catch + re-assert ErrorActionPreference/ProgressPreference (config keys
  could clobber preference/automatic variables).
- `Pipeline/MediaPipeline.ps1` -- ass_to_srt.py existence check: de-dup
  candidates, null-guard before Test-Path (clean FATAL instead of binding
  exception).
- `Pipeline/MediaPipeline.ps1` -- progress reload: -LiteralPath + [int] field
  coercion (partial-file / bracketed-path safety).
- `Pipeline/MediaPipeline/remux.ps1` -- surface mkvmerge stdout (Output) tail
  on exit-code-1 warnings. Behaviour unchanged: exit 1 still publishes.
- `Pipeline/MediaPipeline.ps1` -- declare `$logLock = $null` before the
  ExitCleanup closure.
- `Pipeline/MediaPipeline.ps1` -- PS7 relaunch: default null `$LASTEXITCODE`
  to 1 so a failed relaunch is not reported as success.
- `Pipeline/MediaPipeline.ps1` -- rename resolved `$configPath` ->
  `$resolvedConfigPath` (stop reassigning the `$ConfigPath` parameter via its
  case-variant); updated 3 downstream consumers.
- `Pipeline/MediaPipeline.ps1` -- collapse 7 redundant array-coercion
  `elseif/else` branches to `if/else` (no behaviour change).

Ollama: not used this session.

Validation performed (agent-side):
- Baseline + per-cut `Invoke-EndToEndSmokeChecks.ps1`: exit 0 each time.
- `Invoke-ConfigKeyRegistryChecks.ps1`: passed (130 keys).
- Parser parse-check after every edit: clean.
- Integration: `pwsh -File MediaPipeline.ps1 -ValidateOnly` against the live
  config -> exit 0, "PIPELINE SHUTDOWN CLEANLY", "ass_to_srt import: OK", all
  config keys loaded, no reserved-key warnings.

NOT self-certified (AGENTS.md §7 -- config/settings and FFmpeg/publish paths):
operator validation still required before declaring §7-safe:
- Representative real-media remux that produces a mkvmerge exit-1 warning, to
  confirm the new warning-tail logging (remux.ps1) and that publish behaviour
  is unchanged.
- A real continuous/`-Once` run (this session only ran `-ValidateOnly`).
- `python scripts/dev/ai_guardrail.py` and, per AGENTS.md §5 media row,
  the release gate / real-media validation worksheet.

Not mine / left untouched: stray untracked `CON` file at repo root (pre-existing;
never staged).
