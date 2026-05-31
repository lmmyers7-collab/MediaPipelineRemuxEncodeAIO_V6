# Phase 12 Migration, Rollback, And Cleanup Plan

Last updated: 2026-05-31

This note captures the final Phase 12 migration and cleanup posture. It is a
plan, not approval to remove compatibility code or change production behavior.

## Current Migration State

The rewrite is additive through Phase 12.

| Area | Current state |
| --- | --- |
| Production execution | Legacy PowerShell route and execution path remains authoritative. |
| Settings preview | Backend-owned dry-run `pipeline_plan.v1` preview exists. |
| Planner execution | New Python planner is preview-only for Settings and tests. |
| PowerShell plan executor | Dry-run/parity harness only. |
| Preset write format | `PRESET_POLICY_WRITE_FORMAT = legacy`. |
| Saved config keys | Existing PSD1/JSON keys remain compatibility keys. |
| Rollout | Defaults to legacy authority and dry-run-only evidence. |
| Publish behavior | Existing production publish/drain behavior unchanged. |

No Phase 12 step migrates saved configs, flips defaults, launches jobs through
the new planner, or deletes old code.

## Legacy To V2 Policy Path

The compatibility path is:

```text
legacy flat config
-> preset_v2_from_legacy_config(...)
-> PresetV2
-> EffectiveDecisionPolicy
-> ProcessingDecision
-> dry-run PipelinePlan
```

The old keys stay valid. The v2 view gives the UI and tests a structured model
without breaking existing profiles. Unknown legacy values are preserved under
`advanced.legacyPassthrough` so future cleanup can review them rather than
silently dropping them.

## Rollback Notes

For the current Phase 12 state, rollback is documentation/configuration-only:

1. Leave production execution on the legacy PowerShell path.
2. Remove rollout keys or set `PlannerRolloutStage` to `legacy`.
3. Set `UsePythonPlanner`, `EnablePythonPlanner`, `EnableNewPlanner`,
   `PlannerComparisonLogging`, and `NewPlannerCutoverApproved` to false or
   remove them.
4. Keep `PRESET_POLICY_WRITE_FORMAT` as `legacy`.
5. Confirm Settings preview evidence reports `legacy_powershell`,
   `newPlannerExecutionEnabled: false`, and `dryRunOnly: true`.

No source media, output media, queue state, pending-publish manifest, sidecar,
or completed manifest rollback is required for Phase 12 because no mutation
path changed.

## Future Cutover Prerequisites

Production cutover is still blocked. A later operator-approved phase must prove
all of the following before real jobs use the new planner as authority:

- zero unexplained old/new planner divergences across the route matrix;
- documented and operator-approved intentional divergences;
- live old-path/new-path comparison evidence, not only compatibility fields
  inside the Python decision snapshot;
- Phase 07B command parity evidence for concrete command construction;
- Local API/WebView operator-surface proof;
- route, audio, subtitle, pending-publish, queue, and process-control tests
  appropriate to the touched surfaces;
- full release gate when package behavior is affected;
- representative real-media validation covering remux, encode/size, subtitle,
  audio, deferred publish/final placement, and rollback behavior.

## Cleanup Candidates

Cleanup may begin only after human approval. The table below lists candidate
families and the required posture before deletion.

| Candidate | Safe cleanup gate |
| --- | --- |
| Obsolete labels/constants | New labels accepted, old labels no longer referenced by active UI/API/tests, active doc references pass. |
| Old UI components replaced by the new editor | New editor is production-owned, browser/static smokes pass, and fallback UI is no longer needed. |
| Unused schema paths | Schema usage inventory proves no Local API, WebView, PowerShell profile, or release package consumer reads them. |
| Duplicated decision logic | Python decision authority is cut over, shadow comparison has no unresolved divergences, and PowerShell no longer needs the duplicate policy branch. |
| Compatibility adapters | Saved-config migration is complete, rollback window is closed, and operator approves removal of old key support. |
| Stale tests superseded by stronger tests | Replacement test covers the same behavior and high-risk validation rung; do not remove real-media or mutation guard tests just because metadata tests exist. |
| Dry-run-only fallback placeholders | Real executor fallback behavior is implemented, tested, and documented with operator approval. |
| Deprecated docs in the rewrite subtree | Tracker and canonical docs no longer reference them, and the archive path is explicitly chosen. |

Do not delete compatibility code in the same phase that first promotes a new
runtime path. Keep rollback simple until production evidence is stable.

## Maintenance Plan

After source changes:

- run `DesktopApp\Runtime\Python\python.exe scripts\dev\refresh_summaries.py`;
- run `DesktopApp\Runtime\Python\python.exe scripts\dev\generate_project_index.py --check`;
- run `DesktopApp\Runtime\Python\python.exe scripts\dev\check_active_doc_references.py`;
- run the focused tests for the touched domain;
- run guardrail preflight/postflight and compare against the baseline.

After docs-only changes in this subtree:

- inspect the rendered Markdown where practical;
- run `DesktopApp\Runtime\Python\python.exe scripts\dev\check_active_doc_references.py`;
- run guardrail postflight or the smallest safe subset of generated-context
  checks.

After high-risk behavior changes:

- follow `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`;
- rerun representative real-media validation when media policy, FFmpeg,
  subtitle, audio, publish/drain, source/scratch/output movement, or cleanup
  behavior changes.

## Future Improvements

Post-rewrite work that should remain separately scoped:

- client-specific Plex compatibility profiles;
- real HandBrake preset import/export if useful;
- quality sampling or visual metric checks;
- per-library presets;
- per-series/movie overrides;
- advanced HDR tone-mapping policy;
- hardware capability detection;
- queue-level throughput estimates;
- encode cost estimator.
