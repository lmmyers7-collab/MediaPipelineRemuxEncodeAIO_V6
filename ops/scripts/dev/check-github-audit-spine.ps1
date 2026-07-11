param(
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
} else {
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
}

$RequiredFiles = @(
    ".github/dependabot.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/audit-sarif.yml",
    ".github/workflows/deep-audit.yml",
    ".github/workflows/phase1-drift.yml",
    ".github/workflows/private-beta-windows.yml",
    ".github/ISSUE_TEMPLATE/ai-audit-finding.yml",
    ".github/ISSUE_TEMPLATE/ai-fix-task.yml",
    ".github/pull_request_template.md",
    ".github/copilot-instructions.md",
    ".github/audit-labels.json",
    ".github/GITHUB_AUDIT_BOOTSTRAP.md",
    "ops/scripts/release/Initialize-CiPythonRuntime.ps1",
    "ops/scripts/dev/bootstrap-github-audit-spine.ps1"
)

foreach ($RelativePath in $RequiredFiles) {
    $FullPath = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $FullPath)) {
        throw "Required GitHub audit spine file is missing: $RelativePath"
    }
}

$LabelsPath = Join-Path $RepoRoot ".github/audit-labels.json"
$Labels = Get-Content -LiteralPath $LabelsPath -Raw | ConvertFrom-Json
$LabelNames = @($Labels | ForEach-Object { [string]$_.name })

foreach ($RequiredLabel in @("audit", "ai-ready", "needs-triage", "needs-repro", "validation-needed")) {
    if ($LabelNames -notcontains $RequiredLabel) {
        throw "Missing required audit label: $RequiredLabel"
    }
}

foreach ($RequiredPrefix in @("risk:", "area:", "source:")) {
    if (-not ($LabelNames | Where-Object { $_.StartsWith($RequiredPrefix, [System.StringComparison]::Ordinal) })) {
        throw "Missing required audit label prefix: $RequiredPrefix"
    }
}

$DependabotConfig = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/dependabot.yml") -Raw
if ($DependabotConfig -notmatch "package-ecosystem:\s+pip[\s\S]*?directory:\s+/requirements") {
    throw "Dependabot pip updates must target /requirements so the dependency graph job does not scan an unsupported repo-root manifest."
}

$CodeqlWorkflow = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/workflows/codeql.yml") -Raw
foreach ($Expected in @("python", "javascript-typescript", "rust", "actions", "security-events: write", "CODEQL_UPLOAD_MODE: always", "upload: always", "codeql-results", "upload-artifact", "GITHUB_STEP_SUMMARY")) {
    if ($CodeqlWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "CodeQL workflow is missing expected token: $Expected"
    }
}
foreach ($Forbidden in @('Path(''${{ matrix.language }}'')', 'upload mode: ${{ vars.CODEQL_UPLOAD_MODE', 'vars.CODEQL_UPLOAD_MODE', 'upload: never')) {
    if ($CodeqlWorkflow -match [regex]::Escape($Forbidden)) {
        throw "CodeQL workflow still interpolates GitHub expressions inside a run block: $Forbidden"
    }
}

foreach ($WorkflowPath in @(".github/workflows/phase1-drift.yml", ".github/workflows/deep-audit.yml")) {
    $Workflow = Get-Content -LiteralPath (Join-Path $RepoRoot $WorkflowPath) -Raw
    if ($Workflow -match [regex]::Escape('${{ runner.temp }}')) {
        throw "Workflow must not use runner.temp at job scope: $WorkflowPath"
    }
    foreach ($Expected in @("Use runner temporary directory", 'TMP=$env:RUNNER_TEMP', 'TEMP=$env:RUNNER_TEMP', '$env:GITHUB_ENV')) {
        if ($Workflow -notmatch [regex]::Escape($Expected)) {
            throw "Workflow is missing runtime runner-temp setup token '$Expected': $WorkflowPath"
        }
    }
}

foreach ($WorkflowPath in @(".github/workflows/phase1-drift.yml", ".github/workflows/deep-audit.yml")) {
    $Workflow = Get-Content -LiteralPath (Join-Path $RepoRoot $WorkflowPath) -Raw
    foreach ($JobName in @("release-self-test", "package-verify")) {
        $JobMatch = [regex]::Match($Workflow, "(?ms)^  ${JobName}:\r?\n(?<body>.*?)(?=^  [A-Za-z0-9_-]+:|\z)")
        if (-not $JobMatch.Success) {
            throw "Workflow is missing $JobName job: $WorkflowPath"
        }
        foreach ($Expected in @("Prepare isolated LOCALAPPDATA", 'LOCALAPPDATA=$ciLocalAppData', "MediaPipelineRemuxEncodeAIO", '$env:RUNNER_TEMP', '$env:GITHUB_ENV')) {
            if ($JobMatch.Groups['body'].Value -notmatch [regex]::Escape($Expected)) {
                throw "$JobName job is missing isolated LOCALAPPDATA token '$Expected': $WorkflowPath"
            }
        }
    }
}

$SarifWorkflow = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/workflows/audit-sarif.yml") -Raw
foreach ($Expected in @("ruff", "semgrep", "upload-sarif", "upload-artifact", "GITHUB_STEP_SUMMARY", "security-events: write")) {
    if ($SarifWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "Audit SARIF workflow is missing expected token: $Expected"
    }
}
if ($SarifWorkflow -match "gh\s+issue\s+create") {
    throw "Audit SARIF workflow must not auto-create GitHub issues."
}

$DeepAuditWorkflow = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/workflows/deep-audit.yml") -Raw
foreach ($Expected in @("ai_guardrail", "audit_checks run deep-audit", "unittest discover", "webview:prework:check", "npm run check", "build.ps1")) {
    if ($DeepAuditWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "Deep audit workflow is missing expected token: $Expected"
    }
}
foreach ($Expected in @("permissions:", "contents: read", "Initialize-CiPythonRuntime.ps1 -InstallDependencies", "Initialize-CiMediaTools.ps1 -InstallMissing", "Use runner temporary directory", 'TMP=$env:RUNNER_TEMP', 'TEMP=$env:RUNNER_TEMP', '$env:GITHUB_ENV', "timeout-minutes: 60", "timeout-minutes: 90")) {
    if ($DeepAuditWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "Deep audit workflow is missing expected hardening token: $Expected"
    }
}

$Phase1Workflow = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/workflows/phase1-drift.yml") -Raw
foreach ($Expected in @("permissions:", "contents: read", "MP_GITHUB_BASE_REF", "Initialize-CiPythonRuntime.ps1 -InstallDependencies", "Initialize-CiMediaTools.ps1 -InstallMissing", "Use runner temporary directory", 'TMP=$env:RUNNER_TEMP', 'TEMP=$env:RUNNER_TEMP', '$env:GITHUB_ENV', "timeout-minutes: 60", "timeout-minutes: 90", "audit_checks run phase1-generated")) {
    if ($Phase1Workflow -notmatch [regex]::Escape($Expected)) {
        throw "Generated drift workflow is missing expected hardening token: $Expected"
    }
}
foreach ($Forbidden in @('${{ github.event_name }}" -eq', 'git fetch origin "${{ github.base_ref }}')) {
    if ($Phase1Workflow -match [regex]::Escape($Forbidden)) {
        throw "Generated drift workflow still interpolates GitHub expressions inside a run block: $Forbidden"
    }
}

$PrivateBetaWorkflow = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/workflows/private-beta-windows.yml") -Raw
foreach ($Expected in @("actions: read", "contents: write", "Validate workflow inputs", "MEDIAPIPELINE_RELEASE_REPOSITORY", "Initialize-CiPythonRuntime.ps1")) {
    if ($PrivateBetaWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "Private beta workflow is missing expected hardening token: $Expected"
    }
}
foreach ($Forbidden in @('-Channel ''${{ inputs.channel }}''', '-Repository ''${{ github.repository }}''', '$tag = ''${{ inputs.release_tag }}''')) {
    if ($PrivateBetaWorkflow -match [regex]::Escape($Forbidden)) {
        throw "Private beta workflow still interpolates GitHub expressions inside a run block: $Forbidden"
    }
}

$PrTemplate = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/pull_request_template.md") -Raw
foreach ($Expected in @("Change Packet", "Validation", "Safety Notes", "Scanner Impact")) {
    if ($PrTemplate -notmatch [regex]::Escape($Expected)) {
        throw "Pull request template is missing expected section: $Expected"
    }
}

$CopilotInstructions = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/copilot-instructions.md") -Raw
foreach ($Expected in @("AGENTS.md", "change packet", "source media", "Strict JSON")) {
    if ($CopilotInstructions -notmatch [regex]::Escape($Expected)) {
        throw "Copilot instructions are missing expected guidance: $Expected"
    }
}

Write-Host "GitHub audit spine config passed."
