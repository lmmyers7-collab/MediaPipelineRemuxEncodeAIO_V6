[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$SourceFile,

    [Parameter(Mandatory)]
    [string]$OutputFile,

    [int]$TimeoutSeconds = 180,
    [int]$AppendTimeoutSeconds = 180,
    [int]$CloseTimeoutSeconds = 30,
    [string]$WindowTitle = 'MediaPipelineRemuxEncodeAIO',
    [AllowEmptyString()]
    [string]$SampleValidationLog = '',
    [string]$Decision = 'hold_review',
    [string]$Category = 'h264-remux-safe'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$message = @(
    'PG-2 automatic sample-validation append is disabled because caller-provided paths cannot establish media or backend evidence.'
    'No Tauri shell, backend, pipeline command, or sample-validation append was started.'
    'Use Home -> Sample Validation -> Preview (/api/sample-validation/preview), inspect current Queue/Completed/Pending/Diagnostics evidence and the named files, then append only through the operator-controlled WebView flow.'
    'Automation may be restored only after a backend-authored, run-bound provenance projection is implemented and validated.'
) -join ' '

throw $message
