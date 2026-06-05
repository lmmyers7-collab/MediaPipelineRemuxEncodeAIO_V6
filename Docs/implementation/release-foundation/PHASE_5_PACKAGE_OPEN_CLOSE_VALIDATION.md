# Phase 5 - Package Open/Close Validation

## Goal

Prove the named portable candidate opens and closes through the packaged
Tauri/WebView2 path on a clean Windows account or separate Windows machine.

## Scope

- Release self-test on the copied candidate.
- Packaged Tauri launch/close.
- PG-3 clean-machine report.
- Selected no-mutation WebView and Local API smokes.
- Runtime-state externalization evidence after packaged launch/close.

## Prerequisites

- Read the required context docs listed in `AGENTS.md`.
- Confirm the Phase 4 candidate folder exists outside the repository.
- Confirm the candidate manifest identifies `2026.06.04.001` and includes the Tauri
  preview binary.
- Confirm the candidate was not built with `-KeepPersonalConfig`.
- Confirm the expected runtime/state root for this validation run is outside the
  copied install folder, or stop and resolve the package/runtime configuration
  before launching.
- Stop if the candidate folder, manifest, bundled runtimes, Tauri shell checks,
  or smoke wrappers are missing.

## Steps

1. Copy or unzip the candidate to the clean validation environment.
2. Run `ops\scripts\dev\verify-env.bat`.
3. Run the release self-test against the candidate.
4. Run packaged Tauri launch/close validation.
5. Generate the PG-3 report.
6. Run selected no-mutation smokes.
7. Confirm no backend, Tauri shell, FFmpeg, ffprobe, or MKVToolNix processes
   remain unexpectedly after close.
8. Confirm packaged launch did not create runtime state, live config, queue
   state, pending manifests, run logs, scratch, or output artifacts under the
   install folder.

Do not repair a failed candidate in place. If package/open/close validation
fails, reject this candidate and return to the appropriate earlier phase.

## Commands

From the copied candidate root:

```powershell
.\ops\scripts\dev\verify-env.bat

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1

.\apps\desktop\tauri\Test-TauriShell-Prereqs.ps1 -CheckOnly
.\apps\desktop\tauri\Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30
.\apps\desktop\tauri\New-TauriShell-PG3CleanMachineReport.ps1 -PrereqPassed -LaunchPassed -OperatorConfirmedNoDeveloperTools -Operator "<name>" -Notes "2026.06.04.001 portable candidate"
```

Suggested no-mutation smokes:

```powershell
.\ops/scripts/smoke\Test-LocalApiLifecycleContractSmoke.ps1
.\ops/scripts/smoke\Test-LocalApiMaintenanceDryRunContractSmoke.ps1
.\ops/scripts/smoke\Test-LocalApiSampleValidationContractSmoke.ps1
.\ops/scripts/smoke\Test-WebViewCommandEvidenceSmoke.ps1
.\ops/scripts/smoke\Test-WebViewRealMediaEvidenceSmoke.ps1
.\ops/scripts/smoke\Test-WebViewRowDetailSmoke.ps1
```

Run browser-backed smokes when Chrome or Edge is present. Minimum browser-backed
coverage for accepting the candidate:

```powershell
.\ops/scripts/smoke\Test-WebViewBrowserLifecycleSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserPendingDrainGuardSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserCompletedPendingProofSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserSettingsLaunchSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserSampleValidationSmoke.ps1
```

If browser-backed smokes cannot run in the validation environment, record the
exact blocker and residual package-validation risk.

Run strict change-packet coverage from the source Git checkout after sanitized
Phase 5 evidence is recorded. Do not run strict coverage from the copied
candidate because release packages intentionally omit `.git` metadata:

```powershell
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py --require-worktree-coverage
```

## Change Ledger And Rollback

- Create or update one change packet for this phase before edits or evidence
  capture.
- Record candidate folder, manifest path, PG-3 report path, smoke results,
  process-cleanup evidence, runtime-state root, and install-folder no-state
  evidence.
- Roll back by marking the candidate rejected and discarding generated
  validation artifacts for this candidate. Do not mutate source media or patch
  the copied candidate in place.

## Exit Criteria

- Candidate passes release self-test.
- Packaged Tauri opens, validates backend health/contract/assets, and closes.
- PG-3 report has zero bundle layout mismatches.
- Runtime state resolves outside the install folder, and no package-local state,
  config, scratch, output, pending-publish, or run-log artifacts were created by
  validation.
- No selected smoke posts unintended mutation routes.
- Any developer-tool dependency on the validation machine is explained before
  accepting the candidate.


