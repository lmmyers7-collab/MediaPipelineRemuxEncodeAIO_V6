# Phase 5 - Package Open/Close Validation

## Goal

Prove the named portable candidate opens and closes through the packaged
Tauri/WebView2 path on a clean Windows account or separate Windows machine.

## Scope

- Release self-test on the copied candidate.
- Packaged Tauri launch/close.
- PG-3 clean-machine report.
- Selected no-mutation WebView and Local API smokes.

## Steps

1. Copy or unzip the candidate to the clean validation environment.
2. Run `scripts\verify-env.bat`.
3. Run the release self-test against the candidate.
4. Run packaged Tauri launch/close validation.
5. Generate the PG-3 report.
6. Run selected no-mutation smokes.
7. Confirm no backend, Tauri shell, FFmpeg, ffprobe, or MKVToolNix processes
   remain unexpectedly after close.

## Commands

From the copied candidate root:

```powershell
.\scripts\verify-env.bat

.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\release\test.ps1

.\DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1 -CheckOnly
.\DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30
.\DesktopApp\tauri_shell\New-TauriShell-PG3CleanMachineReport.ps1 -PrereqPassed -LaunchPassed -OperatorConfirmedNoDeveloperTools -Operator "<name>" -Notes "V6.0.0 portable candidate"
```

Suggested no-mutation smokes:

```powershell
.\SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1
.\SmokeTests\Test-LocalApiMaintenanceDryRunContractSmoke.ps1
.\SmokeTests\Test-LocalApiSampleValidationContractSmoke.ps1
.\SmokeTests\Test-WebViewCommandEvidenceSmoke.ps1
.\SmokeTests\Test-WebViewRealMediaEvidenceSmoke.ps1
.\SmokeTests\Test-WebViewRowDetailSmoke.ps1
```

Run browser-backed smokes when Chrome or Edge is present.

## Exit Criteria

- Candidate passes release self-test.
- Packaged Tauri opens, validates backend health/contract/assets, and closes.
- PG-3 report has zero bundle layout mismatches.
- No selected smoke posts unintended mutation routes.
- Any developer-tool dependency on the validation machine is explained before
  accepting the candidate.

