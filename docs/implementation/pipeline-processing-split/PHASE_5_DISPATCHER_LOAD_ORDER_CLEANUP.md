# Phase 5 - Dispatcher, Load Order, And Cleanup

## Goal

After remux and encode internals are split and validated, clean up the
remaining transition scaffolding without changing behavior.

This phase should make the new structure boring:

- module loader is explicit
- entrypoint wrappers are thin
- dispatcher is still the dispatcher
- generated summaries and inventories are current
- old dead helper blocks are removed only when tests prove they are unused

## Scope

In scope:

- Reduce `entrypoints/MediaPipeline/encode.ps1` and `remux.ps1` to wrappers if
  not already done.
- Confirm `pipeline_processing.ps1` still only dispatches.
- Confirm `module_loader.ps1` loads every new module exactly once.
- Remove duplicate helper code left behind by extraction.
- Refresh generated summaries.
- Update docs and inventories where required.

Out of scope:

- Renaming `Do-Encode` or `Do-Remux`.
- Changing queue engine behavior.
- Changing stage contracts.
- Changing Python orchestration.
- Changing WebView controls.

## Context Brief For Fresh Agents

Earlier phases should already have moved encode/remux mechanics. This phase is
not a refactor playground. It is a consolidation pass that removes transition
duplication and locks in discoverability.

## Tasks

1. Confirm no duplicate public definitions.

   ```powershell
   rg -n "function Do-Encode|function Do-Remux|function Invoke-MediaPipelineEncode|function Invoke-MediaPipelineRemux" ops/pipeline
   ```

2. Confirm module loader entries exist and are in dependency order.

   ```powershell
   rg -n "encode_|remux_|PipelineProcessing|PipelinePlanExecutor" `
     ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1
   ```

3. Confirm `pipeline_processing.ps1` still dispatches to the public functions
   and does not grow encode/remux mechanics.

4. Confirm entrypoint child files are wrappers or intentionally retained
   compatibility surfaces.

5. Remove dead transition helpers only after `rg` proves no callers.

6. Refresh generated summaries:

   ```powershell
   .\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
     mediapipeline.tools.dev.refresh_summaries --changed
   ```

7. Update `docs/generated/PROJECT_INDEX.md` or other generated maps only
   through the owning generator if required. Do not hand-edit generated files.

8. Update `docs/DOCS_INDEX.md` only if active docs are added or removed.

9. Run full required validation from `VALIDATION.md`.

10. Confirm worker-child paths still use the same wrappers and module graph:

   ```powershell
   rg -n "SingleFile|WorkerChild|DrainPendingPushes|Invoke-MediaPipelineProcessFile" `
     ops/pipeline/entrypoints/MediaPipeline.ps1 `
     ops/pipeline/engine/queue/pipeline_engine.ps1
   ```

   Follow the scan with the non-mutating load-order harness from
   `VALIDATION.md`. The drain-only path must be proven by stopping before
   `Invoke-RetryPendingPushes` or by stubbing it to fail on invocation. Do not
   run a live pending-publish drain only to validate module load order.

## Validation

Minimum:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-ReliabilityRegressionChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-ToolIntegrationChecks.ps1
```

Also run all targeted unit wrappers affected by the split:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PipelinePlanExecutorChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-EncodeFlagPolicyChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-EncodeSizeGuardInspectionChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-AudioPolicyChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-SubtitleBuilderDecisionChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-MediaVerificationSafetyChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-FFmpegProgressChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerSlotChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerClaimLifecycleChecks.ps1
```

Run adversarial review before final acceptance:

```text
docs/implementation/pipeline-processing-split/ADVERSARIAL_REVIEW.md
```

## Exit Criteria

- No duplicated active implementation remains in old and new files.
- Public wrappers are intentionally thin or explicitly justified.
- Module loader has deterministic load order.
- Worker-child `-SingleFile` and drain-only paths load the same module graph,
  proven without live drain mutation.
- Generated summaries are current.
- Change packet coverage passes.
- Real-media validation status is recorded.
- Adversarial review has no unresolved blocker or high-severity findings.

## Common Pitfalls

- Removing wrappers before all callers are updated.
- Assuming a function is unused because no direct caller exists; PowerShell can
  invoke by name from tests or worker-child paths.
- Hand-editing generated summaries.
- Treating docs/index drift as optional.
- Forgetting local worker slots launch child `MediaPipeline.ps1 -SingleFile`,
  which must load the same module graph.
- Treating a successful live `-DrainPendingPushes` run as a harmless loader
  check. It can move parked media and is not acceptable as load-order proof.
