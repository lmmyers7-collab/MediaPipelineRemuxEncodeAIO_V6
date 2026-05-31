# Phase 09 Verification, Size Guards, and Publish Gates

Date: 2026-05-30

Scope: additive Python/WebView modeling for post-process verification and
publish gates. This phase does not change production PowerShell execution,
FFmpeg command generation, subtitle/audio execution, pending-publish drain,
source/scratch/output movement, cleanup, queue launch behavior, command
journal behavior, settings persistence, or Tauri lifecycle behavior.

## Phase Confirmations

- Approved docs and tracker location: `Docs/rewrite/handbrake-remux/`
- Edit domain for this phase: Python contracts/decision/planner/API preview
  output under `app/`, Settings WebView display wiring, the Phase 07B
  PowerShell dry-run plan validator allowlist, backend readiness/sample
  validation display labels, targeted tests, generated WebView and
  summaries/index context, and this approved rewrite docs/tracker subtree.
- High-risk areas touched: yes. Verification, Output Size Check, publish
  gating, pending-publish semantics, settings guard terminology, and
  media-safety evidence are AGENTS.md high-risk concepts. The implementation
  remains additive/dry-run/reporting-only and does not alter production
  publish/drain behavior.

## Inputs Read

- `AGENTS.md`
- `Docs/CURRENT_PROJECT_STATE.md`
- `OPEN_WORK_CHECKLIST.md`
- `Docs/generated/PROJECT_INDEX.md`
- `Docs/audits/latest.md`
- `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `Docs/rewrite/handbrake-remux/00_execution_tracker.md`
- `Docs/rewrite/handbrake-remux/01_repo_audit.md` through
  `Docs/rewrite/handbrake-remux/08_ui_plan.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/09_VERIFICATION_SIZE_GUARDS_AND_PUBLISH.md`

## Current Behavior Audited

Existing production behavior remains PowerShell-owned:

- Encode verifies output existence, non-empty output, duration sanity, and
  Output Size Check before publish in `Pipeline/MediaPipeline/encode.ps1`.
- Current `SizeGuardMode=advisory` records a warning when an encoded output
  exceeds the growth limit but lets the job continue.
- Current `SizeGuardMode=strict` fails the job before publish through
  `ENCODE_SIZE_GUARD_EXCEEDED`; this is modeled as `fail_job` to preserve
  current behavior.
- Current `SizeGuardMode=off` disables the check.
- Existing unsafe final placement still uses the pending-publish park/drain
  flow in `engine/publish/publish_completion.ps1` and
  `engine/publish/pending_*.ps1`.

This phase did not modify those production PowerShell publish/drain files. The
only PowerShell edit was an allowlist update in the dry-run
`pipeline_plan.v1` validator so existing Phase 07B dry-run checks continue to
accept the expanded plan contract.

## Implemented Contract

New contract: `app/contracts/verification.py`

It defines:

- `VerificationGuard` with `name`, `stage`, `enforcement`, `condition`,
  `onPass`, `onFail`, and `message`.
- `OutputSizeCheck` with explicit action/status, source size, target output
  size, growth tolerance, actual output size, overage bytes/percent, and
  failure action.
- `VerificationResult` with separate `advisoryWarnings`, `failures`, and
  `publishBlockers`.
- Pure helpers for mapping legacy settings to explicit actions and evaluating
  actual size-check outcomes in tests.

Explicit Output Size Check actions are:

| Action | Meaning |
| --- | --- |
| `disabled` | Do not evaluate output growth. |
| `warn_only` | Record advisory warning and continue publish safety checks. |
| `block_publish` | Preserve output and park through existing pending-publish flow. |
| `fail_job` | Fail the job before publish using current failure handling. |

Legacy mapping:

- `off` -> `disabled`
- `advisory` -> `warn_only`
- `strict` -> `fail_job`

`block_publish` is modeled for v2 policy/dry-run plans, but production
promotion still requires a separate PowerShell publish/drain implementation
phase before it can act on real jobs.

## Decision And Plan Wiring

`ProcessingDecision` now carries:

- `verificationRequirements`
- `verificationGuards`
- `verificationResult`
- `publishRequirements`

`PipelinePlan` now carries:

- `verificationRequirements`
- `verificationGuards`
- `verificationResult`
- `publishRequirements`

The planner keeps the same dry-run/non-executable authority. Plans can now show
whether Output Size Check would warn, block publish, fail job, or be disabled,
without running tools or touching media.

## UI Wiring

The Settings WebView now renders backend `pipeline_plan.v1` verification and
publish fields in the existing dry-run preview:

- Output Size Check action/status.
- target output size, growth tolerance, and post-process actual-output
  placeholder.
- verification guards and their `onFail` action.
- publish requirements, including pending-publish use for block-publish
  outcomes.

User-facing Settings terminology now uses `Output Size Check` instead of
ambiguous size-guard wording. The legacy setting key remains `SizeGuardMode`
for compatibility.

Backend-served readiness and sample-validation labels were updated to the same
display term so WebView fixtures and policy-readiness rows agree with the
Settings wording.

## Acceptance Notes

- Warn-only behavior is modeled as advisory evidence, not a publish blocker.
- Block-publish behavior is modeled as a publish blocker whose `onFail` is
  `park_pending_publish`, explicitly reusing the existing park/drain flow.
- Fail-job behavior is modeled separately from publish blocking.
- Advisory warnings, failures, and publish blockers are separate fields in the
  verification result.
- No production route, encode, publish, drain, or source movement path was
  changed.

## Validation

Passed:

- `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_verification_contract tests.contract.test_preset_policy_contract tests.decide.test_processing_decision tests.orchestration.test_pipeline_planner DesktopApp.tests.test_settings_pipeline_plan_preview DesktopApp.tests.test_webview_handbrake_settings_ui DesktopApp.tests.test_service_config_option_policy`
- `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-PipelinePlanExecutorChecks.ps1`
- `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_api_static_files_policy DesktopApp.tests.test_application_facade_web_static DesktopApp.tests.test_webview_navigation_static DesktopApp.tests.test_webview_frontend_mutation_boundary DesktopApp.tests.test_webview_css_design_tokens DesktopApp.tests.test_webview_handbrake_settings_ui DesktopApp.tests.test_settings_pipeline_plan_preview DesktopApp.tests.test_webview_browser_completed_pending_proof_smoke DesktopApp.tests.test_webview_real_media_smoke`
- `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_settings_risk_policy_rules DesktopApp.tests.test_sample_validation_api DesktopApp.tests.test_webview_settings_live_smoke`
- `npm run webview:prework:check`
- `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File SmokeTests/Test-WebViewSettingsLaunchPolicySmoke.ps1`
- `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File SmokeTests/Test-WebViewSettingsLaunchLiveConfigSmoke.ps1`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/refresh_summaries.py --check`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`

Preflight guardrail before edits:

- `DesktopApp/Runtime/Python/python.exe scripts/dev/ai_guardrail.py preflight --json`
  remained red because `scripts/dev/check_risky_file_registry.py` still
  references removed legacy paths. Summary freshness, project index,
  generated maps/schemas, active doc references, architecture guardrails,
  naming lint, god-file guard, and marketecture guard passed.

Postflight guardrail after edits:

- `DesktopApp/Runtime/Python/python.exe scripts/dev/ai_guardrail.py postflight --json`
  remained red only because `scripts/dev/check_risky_file_registry.py` still
  references removed legacy paths. Summary freshness, project index,
  generated maps/schemas, active doc references, architecture guardrails,
  naming lint, god-file guard, and marketecture guard passed.

## Risks And Follow-Ups

- `block_publish` is a dry-run model only in this pass. Production handling
  still needs explicit operator approval, PowerShell implementation, pending
  publish fixture coverage, and real-media validation.
- Current production `strict` behavior remains fail-job, not park. This phase
  intentionally models it that way to avoid silently changing operator safety
  semantics.
- Real-media validation must be rerun before any future production promotion
  that changes FFmpeg/media-policy, subtitle/audio, publish/drain,
  source/scratch/output movement, or cleanup behavior.

## Next Phase Readiness

Phase 10 can build the end-to-end regression matrix on top of the explicit
guard/result contract. Runtime cutover remains blocked until the operator
approves a separate production implementation and validation plan.
