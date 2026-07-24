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
    "ops/scripts/release/Publish-PrivateBetaGitHubRelease.ps1",
    "ops/scripts/release/Publish-TauriUpdaterChannelPointer.ps1",
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
foreach ($Expected in @("python", "javascript-typescript", "rust", "actions", "security-events: write", "CODEQL_UPLOAD_MODE", "codeql-results", "upload-artifact", "GITHUB_STEP_SUMMARY")) {
    if ($CodeqlWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "CodeQL workflow is missing expected token: $Expected"
    }
}
foreach ($Forbidden in @('Path(''${{ matrix.language }}'')', 'upload mode: ${{ vars.CODEQL_UPLOAD_MODE')) {
    if ($CodeqlWorkflow -match [regex]::Escape($Forbidden)) {
        throw "CodeQL workflow still interpolates GitHub expressions inside a run block: $Forbidden"
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
foreach ($Expected in @("permissions:", "contents: read", "Initialize-CiPythonRuntime.ps1")) {
    if ($DeepAuditWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "Deep audit workflow is missing expected hardening token: $Expected"
    }
}

$Phase1Workflow = Get-Content -LiteralPath (Join-Path $RepoRoot ".github/workflows/phase1-drift.yml") -Raw
foreach ($Expected in @("permissions:", "contents: read", "MP_GITHUB_BASE_REF", "Initialize-CiPythonRuntime.ps1", "audit_checks run phase1-generated")) {
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
foreach ($Expected in @("actions: read", "contents: write", "Validate workflow inputs", "MEDIAPIPELINE_RELEASE_REPOSITORY", "Initialize-CiPythonRuntime.ps1", "Publish-PrivateBetaGitHubRelease.ps1", "Publish-TauriUpdaterChannelPointer.ps1", "Advance and verify updater channel pointer", 'private-beta-windows-${{ github.repository }}-${{ inputs.channel }}', "cancel-in-progress: false", "MEDIAPIPELINE_ALLOW_SAME_COMMIT_REBUILD", "validate-windows:", "sign-windows:", "private_beta_validation_handoff.v1", "Verify validation handoff before secret access", "SkipSecretPresence", "Build signed NSIS updater bundle with step-scoped credentials", "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c")) {
    if ($PrivateBetaWorkflow -notmatch [regex]::Escape($Expected)) {
        throw "Private beta workflow is missing expected hardening token: $Expected"
    }
}

$UpdaterPointerPublisher = Get-Content -LiteralPath (Join-Path $RepoRoot "ops/scripts/release/Publish-TauriUpdaterChannelPointer.ps1") -Raw
foreach ($Expected in @('releases/download/$($script:pointerTag)', 'pointer_remote:prerelease', '--latest=false', 'pointer_endpoint:exact_content', 'channel_json:installer_release_identity')) {
    if ($UpdaterPointerPublisher -notmatch [regex]::Escape($Expected)) {
        throw "Updater channel pointer publisher is missing expected routing guard: $Expected"
    }
}
foreach ($Forbidden in @('-Channel ''${{ inputs.channel }}''', '-Repository ''${{ github.repository }}''', '$tag = ''${{ inputs.release_tag }}''', 'gh release upload', '--clobber')) {
    if ($PrivateBetaWorkflow -match [regex]::Escape($Forbidden)) {
        throw "Private beta workflow still interpolates GitHub expressions inside a run block: $Forbidden"
    }
}

$PrivateBetaPublisher = Get-Content -LiteralPath (Join-Path $RepoRoot "ops/scripts/release/Publish-PrivateBetaGitHubRelease.ps1") -Raw
foreach ($Expected in @('release_tag:version_identity', 'remote:tag_matches_source', 'remote:target_identity', 'assets:immutable_default', 'ProtectedRebuildApproval', '--clobber')) {
    if ($PrivateBetaPublisher -notmatch [regex]::Escape($Expected)) {
        throw "Private beta publisher is missing expected provenance guard: $Expected"
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
