[CmdletBinding()]
param(
    [string]$Repository = $env:GITHUB_REPOSITORY,

    [string[]]$Environments = @('beta-release', 'stable-release'),

    [string[]]$RequiredSecrets = @(
        'TAURI_SIGNING_PRIVATE_KEY',
        'TAURI_UPDATER_PUBLIC_KEY',
        'WINDOWS_CERTIFICATE_BASE64',
        'WINDOWS_CERTIFICATE_PASSWORD'
    ),

    [string[]]$OptionalSecrets = @(
        'TAURI_SIGNING_PRIVATE_KEY_PASSWORD'
    ),

    [switch]$Apply,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$checks = [System.Collections.Generic.List[object]]::new()
$commands = [System.Collections.Generic.List[object]]::new()
$plannedCommands = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Message,
        [ValidateSet('error', 'warning')]
        [string]$Severity = 'error'
    )
    $checks.Add([pscustomobject][ordered]@{
        name = $Name
        ok = $Ok
        severity = $Severity
        message = $Message
    }) | Out-Null
}

function Add-PlannedCommand {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [bool]$WouldMutate
    )
    $plannedCommands.Add([pscustomobject][ordered]@{
        name = $Name
        tool = 'gh'
        args = @($Arguments)
        would_mutate = $WouldMutate
    }) | Out-Null
}

function Resolve-Tool {
    param([string]$Name)
    foreach ($candidate in @("$Name.exe", "$Name.cmd", $Name)) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command -and $command.Source) {
            if ([System.IO.Path]::GetExtension($command.Source) -ieq '.ps1') {
                $siblingCmd = [System.IO.Path]::ChangeExtension($command.Source, '.cmd')
                if (Test-Path -LiteralPath $siblingCmd -PathType Leaf) {
                    return $siblingCmd
                }
            }
            return $command.Source
        }
    }
    return $null
}

function Invoke-CapturedCommand {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments
    )
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    foreach ($arg in $Arguments) {
        $psi.ArgumentList.Add($arg)
    }
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $process = [System.Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $commands.Add([pscustomobject][ordered]@{
        name = $Name
        exit_code = $process.ExitCode
        stdout_tail = if ($stdout.Length -gt 2000) { $stdout.Substring($stdout.Length - 2000) } else { $stdout }
        stderr_tail = if ($stderr.Length -gt 2000) { $stderr.Substring($stderr.Length - 2000) } else { $stderr }
    }) | Out-Null
    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Stdout = $stdout
        Stderr = $stderr
    }
}

function Get-SecretNamesFromJson {
    param([string]$JsonText)
    if ([string]::IsNullOrWhiteSpace($JsonText)) {
        return @()
    }
    try {
        $parsed = $JsonText | ConvertFrom-Json
        return @($parsed | ForEach-Object { [string]$_.name } | Where-Object { $_ })
    } catch {
        return @()
    }
}

Add-Check 'repository:format' ($Repository -match '^[^/\s]+/[^/\s]+$') `
    'Repository must be owner/repo.'
Add-Check 'environments:present' ($Environments.Count -gt 0) `
    'At least one release environment must be specified.'
foreach ($environment in $Environments) {
    Add-Check "environment:name:$environment" ($environment -match '^[A-Za-z0-9_.-]+$') `
        "Environment name must be a GitHub-compatible name: $environment."
}
foreach ($secret in ($RequiredSecrets + $OptionalSecrets)) {
    Add-Check "secret_name:$secret" ($secret -match '^[A-Z0-9_]+$') `
        "Secret names must be uppercase environment variable identifiers: $secret."
}

foreach ($environment in $Environments) {
    Add-PlannedCommand -Name "create_environment:$environment" `
        -Arguments @('api', '--method', 'PUT', "repos/$Repository/environments/$environment") `
        -WouldMutate $true
    Add-PlannedCommand -Name "list_environment_secrets:$environment" `
        -Arguments @('secret', 'list', '--repo', $Repository, '--env', $environment, '--json', 'name') `
        -WouldMutate $false
    foreach ($secret in $RequiredSecrets) {
        Add-PlannedCommand -Name "set_secret_hint:${environment}:$secret" `
            -Arguments @('secret', 'set', $secret, '--repo', $Repository, '--env', $environment) `
            -WouldMutate $true
    }
}

if (-not $Apply) {
    Add-Check 'apply:dry_run' $true 'Dry-run only. Pass -Apply to create/check GitHub environments.' 'warning'
} else {
    $gh = Resolve-Tool 'gh'
    Add-Check 'gh:available' ($null -ne $gh) 'GitHub CLI must be installed and on PATH.'
    if ($gh) {
        $auth = Invoke-CapturedCommand -Name 'gh_auth_status' -FilePath $gh -Arguments @('auth', 'status')
        Add-Check 'gh:authenticated' ($auth.ExitCode -eq 0) 'GitHub CLI must be authenticated.'
        if ($auth.ExitCode -eq 0) {
            foreach ($environment in $Environments) {
                $create = Invoke-CapturedCommand -Name "create_environment:$environment" -FilePath $gh `
                    -Arguments @('api', '--method', 'PUT', "repos/$Repository/environments/$environment")
                Add-Check "environment:exists:$environment" ($create.ExitCode -eq 0) `
                    "GitHub environment must exist or be created: $environment."

                $secretList = Invoke-CapturedCommand -Name "list_environment_secrets:$environment" -FilePath $gh `
                    -Arguments @('secret', 'list', '--repo', $Repository, '--env', $environment, '--json', 'name')
                Add-Check "secrets:list:$environment" ($secretList.ExitCode -eq 0) `
                    "Environment secrets must be listable for $environment."
                $secretNames = Get-SecretNamesFromJson -JsonText $secretList.Stdout
                foreach ($secret in $RequiredSecrets) {
                    Add-Check "secret:required:${environment}:$secret" ($secretNames -contains $secret) `
                        "Required environment secret must exist by name: $environment/$secret."
                }
                foreach ($secret in $OptionalSecrets) {
                    Add-Check "secret:optional:${environment}:$secret" ($secretNames -contains $secret) `
                        "Optional environment secret is recommended when the updater key is encrypted: $environment/$secret." 'warning'
                }
            }
        }
    }
}

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomobject][ordered]@{
    schema_version = 'private_beta_github_release_setup.v1'
    ok = ($errorCount -eq 0)
    apply = [bool]$Apply
    repository = $Repository
    environments = @($Environments)
    required_secrets = @($RequiredSecrets)
    optional_secrets = @($OptionalSecrets)
    error_count = $errorCount
    warning_count = $warningCount
    checks = @($checks)
    planned_commands = @($plannedCommands)
    commands = @($commands)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        if ($Apply) {
            Write-Host "Private beta GitHub release setup checked for $Repository."
        } else {
            Write-Host "Private beta GitHub release setup dry-run passed for $Repository."
        }
    } else {
        Write-Host "Private beta GitHub release setup failed for $Repository."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
    if (-not $Apply) {
        Write-Host 'Planned commands:'
        foreach ($planned in $plannedCommands) {
            Write-Host ("gh {0}" -f ($planned.args -join ' '))
        }
    }
}

if (-not $result.ok) {
    exit 1
}
