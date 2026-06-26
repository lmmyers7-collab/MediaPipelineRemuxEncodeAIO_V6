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
    ".github/ISSUE_TEMPLATE/ai-audit-finding.yml",
    ".github/ISSUE_TEMPLATE/ai-fix-task.yml",
    ".github/pull_request_template.md",
    ".github/copilot-instructions.md",
    ".github/audit-labels.json",
    ".github/GITHUB_AUDIT_BOOTSTRAP.md",
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

$CodeqlWorkflow = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/workflows/codeql.yml") -Raw
foreach ($Expected in @("python", "javascript-typescript", "rust", "actions", "security-events: write")) {
    if ($CodeqlWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "CodeQL workflow is missing expected token: $Expected"
    }
}

$SarifWorkflow = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/workflows/audit-sarif.yml") -Raw
foreach ($Expected in @("ruff", "semgrep", "upload-sarif", "security-events: write")) {
    if ($SarifWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "Audit SARIF workflow is missing expected token: $Expected"
    }
}
if ($SarifWorkflow -match "gh\s+issue\s+create") {
    throw "Audit SARIF workflow must not auto-create GitHub issues."
}

$DeepAuditWorkflow = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/workflows/deep-audit.yml") -Raw
foreach ($Expected in @("ai_guardrail", "unittest discover", "webview:prework:check", "npm run check", "build.ps1")) {
    if ($DeepAuditWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "Deep audit workflow is missing expected token: $Expected"
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
