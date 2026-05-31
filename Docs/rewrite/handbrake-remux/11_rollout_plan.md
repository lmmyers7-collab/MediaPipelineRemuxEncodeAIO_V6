# Phase 11 Rollout, Backwards Compatibility, and Feature Flag

Last updated: 2026-05-31

## Phase Confirmations

- Approved docs/tracker location:
  `Docs/rewrite/handbrake-remux/`, with tracker
  `Docs/rewrite/handbrake-remux/00_execution_tracker.md`.
- Edit domain: Python config/Settings preview tests plus this approved rewrite
  docs/tracker subtree. Production PowerShell execution remains untouched.
- High-risk areas touched: yes, by rollout modeling and config-adjacent
  preview evidence only. This phase does not change FFmpeg command generation,
  stream mapping, subtitle/audio policy, queue launch behavior, publish/drain
  behavior, source/scratch/output movement, command journal behavior, or Tauri
  lifecycle ownership.

## Inputs Read

- `AGENTS.md`
- `Docs/CURRENT_PROJECT_STATE.md`
- `OPEN_WORK_CHECKLIST.md`
- `Docs/generated/PROJECT_INDEX.md`
- `Docs/audits/latest.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/11_ROLLOUT_BACKCOMPAT_AND_FEATURE_FLAG.md`
- `Docs/rewrite/handbrake-remux/00_execution_tracker.md`
- Prior rewrite phase docs `01_repo_audit.md` through `10_test_matrix.md`

## Existing Rollout Controls Located

- Production execution still uses the legacy PowerShell route/execution path.
- `PRESET_POLICY_WRITE_FORMAT` remains `legacy`, so v2 preset policy is not
  the write format.
- The Settings `PipelinePlan` route is dry-run only:
  `/api/settings/pipeline-plan-preview` returns `pipeline_plan.v1`, reports
  `canExecute: false`, does not save config, and does not mutate media.
- The Phase 07B PowerShell plan executor is a dry-run/parity harness, not the
  production execution path.
- Existing config loading is extras-compatible, so rollout keys can be carried
  in the current mapping shape without breaking legacy config reads.

## Rollout Switch Added

`app/config/rollout.py` defines a read-only rollout resolver for the current
config mapping shape. Recognized keys:

| Key | Purpose | Default |
| --- | --- | --- |
| `PlannerRolloutStage` | Stage selector: `legacy`, `shadow`, `selected_jobs`, `ui_old_backend`, `new_planner_default`, or `deprecation_cleanup`. Stage aliases such as `stage1`, `stage2`, and `cutover` are accepted. | `legacy` |
| `UsePythonPlanner`, `EnablePythonPlanner`, `EnableNewPlanner` | Request Python planner rollout behavior. | `false` |
| `EnableHandBrakeSettingsUi`, `EnableHandbrakeSettingsUi`, `EnableNewPlannerUi` | Mark the new UI as enabled while preserving old-safe backend authority. | `false` |
| `PlannerComparisonLogging`, `EnablePlannerComparisonLogging` | Include old/new planner comparison evidence in dry-run previews. | `false` |
| `NewPlannerCutoverApproved`, `PlannerCutoverApproved` | Second explicit key required before the resolver can report cutover-enabled state. | `false` |

The default state is:

- `stage: legacy`
- `executionAuthority: legacy_powershell`
- `newPlannerExecutionEnabled: false`
- `dryRunOnly: true`
- `presetWriteFormat: legacy`

The resolver can report a `python_planner_cutover` state only when a cutover
stage, a new-planner request, and an explicit cutover approval key are all
present. No production caller consumes that state in this phase.

## Preview Observability

The existing Settings `PipelinePlan` preview now adds read-only rollout
evidence under `effectivePresetSnapshot`:

- `rollout`: resolved `planner_rollout.v1` state.
- `plannerComparison`: resolved `planner_comparison.v1` state.

When comparison logging is off, `plannerComparison.status` is `disabled`.
When enabled, it compares the Python route summary against the legacy-route
compatibility field already carried by `ProcessingDecision`. This is dry-run
evidence only; it does not yet represent a live PowerShell old-path log record.

## Backwards Compatibility

- Legacy configs still load through `Config` and `preset_v2_from_legacy_config`.
- Unknown legacy config keys remain preserved under `advanced.legacyPassthrough`
  in the v2 preset view.
- The legacy write posture remains unchanged.
- Existing jobs continue to execute through the legacy PowerShell path.
- The Settings preview route remains non-mutating and can be called without
  saving rollout keys.
- The new rollout keys are extras-compatible and default-safe. They do not
  change route execution unless a future, separately approved cutover wires
  them into launch/execution.

## Rollback Notes

Operator-safe rollback for this phase is configuration-only:

1. Remove rollout keys or set `PlannerRolloutStage = 'legacy'`.
2. Set `UsePythonPlanner`, `EnablePythonPlanner`, `EnableNewPlanner`,
   `PlannerComparisonLogging`, and `NewPlannerCutoverApproved` to false or
   remove them.
3. Confirm Settings `PipelinePlan` preview reports
   `executionAuthority: legacy_powershell`,
   `newPlannerExecutionEnabled: false`, and `dryRunOnly: true`.
4. Keep `PRESET_POLICY_WRITE_FORMAT` as `legacy`.

No source files, media files, queue state, pending-publish manifests, or output
files need rollback for this phase because no mutation path was changed.

## Future Cutover Gate

Before any future phase can make the new planner default or route real jobs
through it, the operator must approve a separate cutover plan and rerun the
AGENTS.md validation ladder for the high-risk media-policy surface:

- zero unexplained old/new planner divergences across the route matrix;
- operator-approved intentional divergences;
- shadow-mode evidence from representative dry-run/live previews;
- Phase 07B executor parity evidence for concrete command construction;
- Local API/WebView operator-surface proof;
- full release gate as appropriate;
- representative real-media validation for remux, encode/size, subtitle,
  audio, pending-publish/final-placement, and rollback behavior.

## Validation

Passed:

```powershell
DesktopApp\Runtime\Python\python.exe -m unittest tests.contract.test_rollout_policy
DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_settings_pipeline_plan_preview
DesktopApp\Runtime\Python\python.exe -m unittest tests.contract.test_rollout_policy tests.contract.test_preset_policy_contract tests.contract.test_source_media_contract tests.contract.test_verification_contract
DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_settings_pipeline_plan_preview DesktopApp.tests.test_webview_frontend_mutation_boundary
DesktopApp\Runtime\Python\python.exe -m unittest tests.integration.test_handbrake_remux_regression_matrix tests.orchestration.test_pipeline_planner
DesktopApp\Runtime\Python\python.exe scripts\dev\refresh_summaries.py --check
DesktopApp\Runtime\Python\python.exe scripts\dev\generate_project_index.py --check
DesktopApp\Runtime\Python\python.exe scripts\dev\check_active_doc_references.py
DesktopApp\Runtime\Python\python.exe scripts\dev\check_architecture_guardrails.py
DesktopApp\Runtime\Python\python.exe scripts\lint-naming.py
DesktopApp\Runtime\Python\python.exe scripts\dev\check_godfiles.py
DesktopApp\Runtime\Python\python.exe scripts\dev\check_marketecture.py
```

Preflight guardrail:

```powershell
DesktopApp\Runtime\Python\python.exe scripts\dev\ai_guardrail.py preflight
DesktopApp\Runtime\Python\python.exe scripts\dev\ai_guardrail.py postflight
```

The guardrail remained red in preflight and postflight from the existing
risky-file registry baseline that still references removed legacy paths.
Summary freshness, generated project index, generated maps/schemas, active doc
references, architecture guardrails, naming lint, god-file guard, and
marketecture guard passed inside both guardrail runs; no changed path matched
the risky-file registry.

## Acceptance Notes

- A clear staged rollout path exists and defaults to legacy execution.
- Legacy users/configs remain safe because no defaults or production execution
  routes changed.
- Decision comparison evidence is inspectable in dry-run Settings previews when
  `PlannerComparisonLogging` is enabled.
- Rollback steps are documented.
- Future cutover remains blocked on operator approval and high-validation
  evidence.

## Risks And Open Questions

- `plannerComparison` currently compares against the Python decision's
  legacy-route compatibility field. A future phase still needs live PowerShell
  old-path difference logging before real cutover.
- The rollout resolver is not wired into Launch or PowerShell execution. This
  is intentional for Phase 11 but means the switch is evidence/config posture,
  not a production behavior switch yet.
- If the operator wants persisted rollout controls in the Settings UI, that
  should be a separate UI/config-schema phase with its own validation.

## Next Phase Readiness

Phase 12 can proceed for final docs/operator guide work. Runtime cutover is not
ready and should not be treated as Phase 12 documentation cleanup unless the
operator separately approves the high-risk cutover plan.
