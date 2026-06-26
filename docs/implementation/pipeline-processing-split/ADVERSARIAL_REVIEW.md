# Adversarial Review - Pipeline Processing Split

## Mindset

After every implementation phase, assume the split failed badly. The goal is to
find the break before an operator finds it during a real encode.

Use this checklist as a required review gate, not as optional polish.

## Review Output Format

Every adversarial review should produce a finding table in the change packet or
phase notes:

| Severity | Finding | Evidence | Required fix | Status |
|---|---|---|---|---|
| blocker/high/medium/low | What is wrong or risky. | File/line, command output, or test name. | Concrete action. | open/fixed/accepted |

Severity guide:

- blocker: unsafe source/output mutation risk, publish corruption risk, partial
  output acceptance, broken startup, missing public function, or unvalidated
  media behavior change.
- high: route/fallback/verification behavior may have changed, but no direct
  destructive mutation is proven.
- medium: troubleshooting evidence, logs, docs, tests, or load-order clarity is
  weaker than before.
- low: wording, naming, or cleanup issue.

Do not close a phase with unresolved blocker or high findings.

## Failure-First Checklist

### Startup And Load Order

- Did `module_loader.ps1` load every new file exactly once?
- Are new modules loaded before wrappers call their functions?
- Does worker-child `-SingleFile` load the same module graph?
- Does `-DrainPendingPushes` still avoid normal scan/processing paths?
- Did any function name collide with an existing function?
- Can tests dot-source modules in isolation, or did new code depend on hidden
  startup side effects?
- If live code delegates to `pipeline_plan_executor.ps1`, is that file loaded
  by `module_loader.ps1` before the caller?
- Do `-SingleFile`, `-WorkerChild`, and `-DrainPendingPushes` use the same
  module graph?

Search:

```powershell
rg -n "function Do-Encode|function Do-Remux|function Invoke-MediaPipelineEncode|function Invoke-MediaPipelineRemux" ops/pipeline
rg -n "encode_|remux_" ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1
```

### Public Contract Preservation

- Does `Invoke-MediaPipelineProcessFile` still call `Do-Encode` for encode and
  `Do-Remux` for remux?
- Do `Do-Encode` and `Do-Remux` still return boolean-like success/failure?
- Does `Do-Remux` still accept and honor `-FallbackFromOversizedEncode` and
  `-FallbackFromDynamicHdrEncode`?
- Do handled failures still register source failures before returning false?
- Do unexpected exceptions still produce failure evidence and avoid publishing?
- Did any caller rely on a script-scoped variable that was made local?

Search:

```powershell
rg -n "Do-Encode|Do-Remux|totalEncoded|totalRemuxed|totalFailed|Register-SourceFailure" `
  ops/pipeline/engine/process ops/pipeline/entrypoints/MediaPipeline
```

### Source And Scratch Safety

- Can any new code write to the original source path?
- Did scratch copy cleanup change?
- Does failed/interrupted encode leave partial output unaccepted?
- Does remux fallback after oversized encode keep the scratch copy available
  long enough?
- Are path-boundary checks still owned by existing storage/path helpers?

Blocker if uncertain.

### FFmpeg And mkvmerge Command Shape

- Did argument order change?
- Did stream maps change?
- Did metadata/title/attachment preservation change?
- Did subtitle burn/copy behavior change?
- Did audio default track flags change?
- Did command repro output still capture enough to rerun the command?
- Is `pipeline_plan_executor.ps1` still in parity with live command builders?

Required evidence:

- targeted command-shape tests
- tool integration when tools are available
- real-media sample if behavior changed

### Fallback Logic

- Does hardware safe retry trigger under the same conditions?
- Does CPU fallback trigger under the same conditions?
- Is CPU mutex always released on success, failure, timeout, and exception?
- Does Dynamic HDR preserve/remux fallback still fail closed?
- Does oversized encode remux fallback still reject when remux is unsafe?
- Are route reason codes updated after fallback success?
- Does Completed evidence distinguish normal encode, safe retry, and CPU
  fallback?

### Verification And Publish

- Can an output publish before verification runs?
- Can a missing or empty output publish?
- Can a multi-video source lose a real video stream and still publish?
- Can Dynamic HDR preserve mode publish without expected metadata?
- Can quality verification errors be ignored in block-review mode?
- Did sidecar candidates survive the new module boundary?
- Did pending publish parking behavior remain owned by publish modules?
- Is there a test that fails if `Complete-PipelineOutputPublish` is called
  before verification and size guard acceptance?

### Progress, Events, And Operator Evidence

- Did progress stages change unexpectedly?
- Did route labels change unexpectedly?
- Did failure codes change unexpectedly?
- Did suggested actions lose useful operator guidance?
- Did repro stage labels change?
- Did event types change?
- Does WebView still have enough evidence to render existing rows?

Search:

```powershell
rg -n "Set-ProgressStage|Write-PipelineEvent|Register-SourceFailure|ReproStage|ErrorCode|SuggestedAction" `
  ops/pipeline/engine/process ops/pipeline/entrypoints/MediaPipeline
```

### Tests And Validation

- Did targeted tests run after the exact files changed?
- Did a broader regression suite run after module loader changes?
- Did `Invoke-AdversarialForceKillEncodeChecks.ps1` run after encode execution
  or publish behavior changed?
- Did real-media validation run after any behavior-affecting media change?
- Did real-media validation run after command/execution movement even when the
  intended change was "mechanical"?
- Are skipped tests explained?
- Does change-packet coverage pass without absorbing unrelated dirty files?

### Documentation And Generated Context

- Did the implementation update or create docs only in active docs locations?
- Did `docs/DOCS_INDEX.md` change if active docs were added or removed?
- Were generated summaries refreshed through tooling after source edits?
- Were generated docs hand-edited by mistake?
- Do docs avoid making this planning pack a new authority over AGENTS,
  architecture, module map, or validation ladder?

## Common Bad Refactor Patterns

Reject these patterns during review:

- "Moved code and cleaned it up" in the same commit.
- Renamed progress/failure stages without a consumer audit.
- Changed command-builder output while calling it a split.
- Introduced a generic `Run-Tool` wrapper that hides FFmpeg/mkvmerge stage
  identity.
- Replaced specific failure handling with one catch-all failure.
- Used string concatenation for paths instead of existing path helpers.
- Added a new state file without updating state inventories and both Python/PS
  ownership.
- Made WebView or Python API decide media behavior.
- Left old implementation and new implementation both active.
- Added tests that pass by mocking away the behavior being split.

## Final Acceptance Gate

Before the whole split is accepted, answer these directly:

1. What files changed, and why does each file own the right responsibility?
2. What public contracts stayed unchanged?
3. What evidence proves command shape did not drift?
4. What evidence proves failed encodes cannot publish partial outputs?
5. What evidence proves remux preserves expected streams and sidecars?
6. What evidence proves pending publish and drain behavior did not drift?
7. What real-media samples were used, and what did they prove?
8. What validation was not run, and why is acceptance still safe or not safe?
9. What rollback would restore the previous behavior?
10. What unrelated dirty files were ignored?

If any answer is weak, do not finalize the phase.
