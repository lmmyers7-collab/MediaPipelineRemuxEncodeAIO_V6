[CmdletBinding()]
param(
    [int]$TimeoutSeconds = 120,
    [int]$CloseTimeoutSeconds = 20,
    [string]$WindowTitle = 'MediaPipelineRemuxEncodeAIO',
    [int]$MaxElements = 220,
    [string]$ExpectedWebView2UserDataFolder = '',
    [switch]$SkipPrimaryNavigationKeyboardProbe
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Resolve-ToolPath {
    param([Parameter(Mandatory)][string]$Name)

    $cmd = Get-Command $Name -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and $_.Source -notmatch '\\WindowsApps\\' } |
        Select-Object -First 1
    if ($cmd -and $cmd.Source) { return [string]$cmd.Source }

    $extraCandidates = @()
    if ($Name -in @('cargo', 'rustc', 'rustup')) {
        $extraCandidates += Join-Path $env:USERPROFILE ".cargo\bin\$Name.exe"
    }
    if ($Name -eq 'node') {
        $extraCandidates += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages') -Recurse -Filter 'node.exe' -ErrorAction SilentlyContinue |
            ForEach-Object { $_.FullName }
    }
    if ($Name -eq 'npm') {
        $extraCandidates += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages') -Recurse -Filter 'npm.cmd' -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\node_modules\\corepack\\' } |
            ForEach-Object { $_.FullName }
    }
    foreach ($candidate in $extraCandidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return [string]$candidate
        }
    }
    return ''
}

function Resolve-VsDevCmd {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
        $installPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null | Select-Object -First 1
        if ($installPath) {
            $candidate = Join-Path $installPath 'Common7\Tools\VsDevCmd.bat'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                return [string]$candidate
            }
        }
    }
    return ''
}

function Get-LocalApiBackendProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            [string]$_.Name -match '^python(\d+(\.\d+)*)?\.exe$' -and
            [string]$_.CommandLine -match 'mediapipeline.desktop\.local_api_main'
        }
}

function Get-TauriShellProcesses {
    Get-Process -Name 'mediapipeline-tauri-shell' -ErrorAction SilentlyContinue
}

function Get-WebView2RootProcesses {
    param([int[]]$ShellProcessIds)

    $ids = @($ShellProcessIds | Where-Object { $_ -gt 0 } | Select-Object -Unique)
    if ($ids.Count -eq 0) { return @() }
    return Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            [string]$_.Name -eq 'msedgewebview2.exe' -and
            $ids -contains [int]$_.ParentProcessId
        }
}

function Get-WebView2UserDataFolder {
    param([Parameter(Mandatory)][string]$CommandLine)

    $match = [regex]::Match(
        $CommandLine,
        '(?:^|\s)--user-data-dir=(?:"(?<quoted>[^"]+)"|(?<bare>\S+))'
    )
    if (-not $match.Success) { return '' }
    $value = if ($match.Groups['quoted'].Success) {
        $match.Groups['quoted'].Value
    } else {
        $match.Groups['bare'].Value
    }
    if (-not $value) { return '' }
    return [System.IO.Path]::GetFullPath($value).TrimEnd('\', '/')
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)
    if (-not $Process -or $Process.HasExited) { return }
    try {
        $Process.Kill($true)
    } catch {
        try { $Process.Kill() } catch { }
    }
}

function Stop-ProcessIdTree {
    param([int]$ProcessId)

    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) { return }
    Stop-ProcessTree -Process $proc
}

function Wait-ProcessIdsGone {
    param(
        [int[]]$ProcessIds,
        [int]$TimeoutSeconds
    )

    $ids = @($ProcessIds | Where-Object { $_ -gt 0 } | Select-Object -Unique)
    if ($ids.Count -eq 0) { return @() }
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $remaining = @($ids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
        if ($remaining.Count -eq 0) { return @() }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $remaining
}

function Get-LogTail {
    param([string]$Path, [int]$LineCount = 80)

    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
    try {
        return (Get-Content -LiteralPath $Path -Tail $LineCount -ErrorAction Stop) -join [Environment]::NewLine
    } catch {
        return "[could not read log tail: $($_.Exception.Message)]"
    }
}

function Get-UiAutomationRows {
    param(
        [Parameter(Mandatory)][IntPtr]$WindowHandle,
        [int]$Limit
    )

    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($WindowHandle)
    if (-not $root) { throw "UI Automation could not read window handle $WindowHandle." }
    $all = $root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    $rows = New-Object System.Collections.Generic.List[object]
    for ($idx = 0; $idx -lt $all.Count -and $rows.Count -lt $Limit; $idx++) {
        $item = $all.Item($idx)
        try {
            $current = $item.Current
            $name = [string]$current.Name
            $automationId = [string]$current.AutomationId
            $controlTypeObject = $current.ControlType
            try {
                $controlType = [string]$controlTypeObject.ProgrammaticName
            } catch {
                $controlType = [string]$controlTypeObject
            }
            $className = [string]$current.ClassName
            $isEnabled = [bool]$current.IsEnabled
            $isOffscreen = [bool]$current.IsOffscreen
            $hasKeyboardFocus = [bool]$current.HasKeyboardFocus
            $itemStatus = [string]$current.ItemStatus
        } catch {
            Write-Verbose "Skipped transient UI Automation element at index ${idx}: $($_.Exception.Message)"
            continue
        }
        if (-not $name -and -not $automationId -and -not $className) { continue }
        $rows.Add([pscustomobject]@{
            Index = $idx
            ControlType = $controlType
            AutomationId = $automationId
            Name = $name
            ClassName = $className
            IsEnabled = $isEnabled
            IsOffscreen = $isOffscreen
            HasKeyboardFocus = $hasKeyboardFocus
            ItemStatus = $itemStatus
        }) | Out-Null
    }
    return $rows
}

function Get-UiAutomationRoot {
    param([Parameter(Mandatory)][IntPtr]$WindowHandle)

    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($WindowHandle)
    if (-not $root) { throw "UI Automation could not read window handle $WindowHandle." }
    return $root
}

function Find-UiAutomationButton {
    param(
        [Parameter(Mandatory)][System.Windows.Automation.AutomationElement]$Root,
        [Parameter(Mandatory)][string]$Name
    )

    $conditions = New-Object System.Windows.Automation.AndCondition(
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::NameProperty,
            $Name
        )),
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Button
        ))
    )
    return $Root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $conditions)
}

function Find-UiAutomationWindow {
    param([Parameter(Mandatory)][string]$Name)

    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    $condition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::NameProperty,
        $Name
    )
    return [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
        [System.Windows.Automation.TreeScope]::Children,
        $condition
    )
}

function Wait-UiAutomationWindow {
    param(
        [Parameter(Mandatory)][string]$Name,
        [int]$TimeoutMilliseconds = 10000
    )

    $deadline = (Get-Date).AddMilliseconds($TimeoutMilliseconds)
    do {
        $window = Find-UiAutomationWindow -Name $Name
        if ($window) { return $window }
        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $deadline)
    return $null
}

function Test-NativeWindowHandle {
    param([Parameter(Mandatory)][IntPtr]$WindowHandle)

    if (-not ('MediaPipelineUiAutomationWindowState' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class MediaPipelineUiAutomationWindowState
{
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern IntPtr GetAncestor(IntPtr hWnd, uint flags);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool PostMessage(IntPtr hWnd, uint message, IntPtr wParam, IntPtr lParam);
}
'@
    }
    return [MediaPipelineUiAutomationWindowState]::IsWindow($WindowHandle)
}

function Get-NativeRootWindowHandle {
    param([Parameter(Mandatory)][IntPtr]$WindowHandle)

    [void](Test-NativeWindowHandle -WindowHandle $WindowHandle)
    return [MediaPipelineUiAutomationWindowState]::GetAncestor($WindowHandle, 2)
}

function Test-NativeWindowVisible {
    param([Parameter(Mandatory)][IntPtr]$WindowHandle)

    [void](Test-NativeWindowHandle -WindowHandle $WindowHandle)
    return [MediaPipelineUiAutomationWindowState]::IsWindowVisible($WindowHandle)
}

function Request-NativeWindowClose {
    param([Parameter(Mandatory)][IntPtr]$WindowHandle)

    [void](Test-NativeWindowHandle -WindowHandle $WindowHandle)
    return [MediaPipelineUiAutomationWindowState]::PostMessage(
        $WindowHandle,
        0x0010,
        [IntPtr]::Zero,
        [IntPtr]::Zero
    )
}

function Wait-PrimaryNavigationState {
    param(
        [Parameter(Mandatory)][IntPtr]$WindowHandle,
        [Parameter(Mandatory)][string]$PageLabel,
        [Parameter(Mandatory)][string]$ButtonLabel,
        [switch]$RequireFocus,
        [switch]$QuietTimeout,
        [int]$TimeoutMilliseconds = 5000
    )

    $deadline = (Get-Date).AddMilliseconds($TimeoutMilliseconds)
    do {
        $root = Get-UiAutomationRoot -WindowHandle $WindowHandle
        $button = Find-UiAutomationButton -Root $root -Name $ButtonLabel
        if (
            $button -and
            ([string]$button.Current.ClassName -split '\s+' -contains 'is-active') -and
            (-not $RequireFocus -or $button.Current.HasKeyboardFocus)
        ) {
            return $true
        }
        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $deadline)
    if (-not $QuietTimeout) {
        $diagnosticRows = @(Get-UiAutomationRows -WindowHandle $WindowHandle -Limit 1000 | Where-Object {
            $_.Name -in @($PageLabel, $ButtonLabel) -or $_.ClassName -match '(^|\s)is-active($|\s)'
        } | Select-Object -First 120)
        Write-Warning "Timed out waiting for page '$PageLabel' and focused nav '$ButtonLabel'. Matches: $($diagnosticRows | ConvertTo-Json -Compress)"
    }
    return $false
}

function Set-UiAutomationForegroundWindow {
    param([Parameter(Mandatory)][IntPtr]$WindowHandle)

    if (-not ('MediaPipelineUiAutomationNativeWindow' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class MediaPipelineUiAutomationNativeWindow
{
    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct GuiThreadInfo
    {
        public int Size;
        public int Flags;
        public IntPtr Active;
        public IntPtr Focus;
        public IntPtr Capture;
        public IntPtr MenuOwner;
        public IntPtr MoveSize;
        public IntPtr Caret;
        public Rect CaretRect;
    }

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, IntPtr processId);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetGUIThreadInfo(uint threadId, ref GuiThreadInfo info);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool PostMessage(IntPtr hWnd, uint message, IntPtr wParam, IntPtr lParam);

    public static IntPtr PostKeyToFocusedWindow(IntPtr topLevelWindow, int virtualKey)
    {
        uint threadId = GetWindowThreadProcessId(topLevelWindow, IntPtr.Zero);
        GuiThreadInfo info = new GuiThreadInfo();
        info.Size = Marshal.SizeOf(typeof(GuiThreadInfo));
        if (!GetGUIThreadInfo(threadId, ref info))
        {
            throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error(), "GetGUIThreadInfo failed.");
        }
        IntPtr target = info.Focus != IntPtr.Zero ? info.Focus : topLevelWindow;
        int scanCode = virtualKey == 0x0D ? 0x1C : 0x39;
        int keyDown = 1 | (scanCode << 16);
        int keyUp = keyDown | unchecked((int)0xC0000000);
        if (!PostMessage(target, 0x0100, new IntPtr(virtualKey), new IntPtr(keyDown)) ||
            !PostMessage(target, 0x0101, new IntPtr(virtualKey), new IntPtr(keyUp)))
        {
            throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error(), "Posting keyboard messages failed.");
        }
        return target;
    }
}
'@
    }
    if (-not [MediaPipelineUiAutomationNativeWindow]::SetForegroundWindow($WindowHandle)) {
        Write-Verbose "SetForegroundWindow did not report success for handle $WindowHandle."
    }
    Start-Sleep -Milliseconds 100
}

function Invoke-PrimaryNavigationClick {
    param(
        [Parameter(Mandatory)][IntPtr]$WindowHandle,
        [Parameter(Mandatory)][string]$ButtonLabel
    )

    $button = $null
    $deadline = (Get-Date).AddSeconds(10)
    do {
        $root = Get-UiAutomationRoot -WindowHandle $WindowHandle
        $button = Find-UiAutomationButton -Root $root -Name $ButtonLabel
        if ($button) { break }
        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $deadline)
    if (-not $button) { throw "UI Automation could not find primary navigation button '$ButtonLabel'." }
    $pattern = $null
    if (-not $button.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
        throw "Primary navigation button '$ButtonLabel' does not expose UI Automation InvokePattern."
    }
    ([System.Windows.Automation.InvokePattern]$pattern).Invoke()
}

function Invoke-PrimaryNavigationKey {
    param(
        [Parameter(Mandatory)][IntPtr]$WindowHandle,
        [Parameter(Mandatory)][string]$ButtonLabel,
        [Parameter(Mandatory)][ValidateSet('Enter', 'Space')][string]$Key
    )

    $button = $null
    $deadline = (Get-Date).AddSeconds(10)
    do {
        $root = Get-UiAutomationRoot -WindowHandle $WindowHandle
        $button = Find-UiAutomationButton -Root $root -Name $ButtonLabel
        if ($button) { break }
        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $deadline)
    if (-not $button) { throw "UI Automation could not find primary navigation button '$ButtonLabel'." }
    Set-UiAutomationForegroundWindow -WindowHandle $WindowHandle
    $button.SetFocus()
    Start-Sleep -Milliseconds 100
    $virtualKey = [int]$(if ($Key -eq 'Enter') { 0x0D } else { 0x20 })
    $targetHandle = [MediaPipelineUiAutomationNativeWindow]::PostKeyToFocusedWindow($WindowHandle, $virtualKey)
    Write-Verbose "Posted $Key to focused window handle $targetHandle."
}

function Invoke-PrimaryNavigationKeyboardProbe {
    param([Parameter(Mandatory)][IntPtr]$WindowHandle)

    $pages = @(
        [pscustomobject]@{ Page = 'home'; Label = 'Home' },
        [pscustomobject]@{ Page = 'launch'; Label = 'Launch' },
        [pscustomobject]@{ Page = 'live'; Label = 'Telemetry' },
        [pscustomobject]@{ Page = 'metrics'; Label = 'Metrics' },
        [pscustomobject]@{ Page = 'queue'; Label = 'Queue' },
        [pscustomobject]@{ Page = 'completed'; Label = 'Completed Output' },
        [pscustomobject]@{ Page = 'pending'; Label = 'Pending Publish' },
        [pscustomobject]@{ Page = 'rename'; Label = 'Rename' },
        [pscustomobject]@{ Page = 'reports'; Label = 'Reports' },
        [pscustomobject]@{ Page = 'network'; Label = 'Network Workers' },
        [pscustomobject]@{ Page = 'libraries'; Label = 'Libraries' },
        [pscustomobject]@{ Page = 'schedule'; Label = 'Schedule' },
        [pscustomobject]@{ Page = 'settings'; Label = 'Settings' },
        [pscustomobject]@{ Page = 'diagnostics'; Label = 'Diagnostics' },
        [pscustomobject]@{ Page = 'maintenance'; Label = 'Maintenance' }
    )
    $cases = New-Object System.Collections.Generic.List[object]
    foreach ($key in @('Enter', 'Space')) {
        for ($idx = 0; $idx -lt $pages.Count; $idx++) {
            $target = $pages[$idx]
            $sentinel = $pages[($idx + 1) % $pages.Count]

            Invoke-PrimaryNavigationClick -WindowHandle $WindowHandle -ButtonLabel $sentinel.Label
            if (-not (Wait-PrimaryNavigationState -WindowHandle $WindowHandle -PageLabel $sentinel.Label -ButtonLabel $sentinel.Label)) {
                throw "UI Automation could not establish sentinel page '$($sentinel.Page)' before $key -> $($target.Page)."
            }

            $activated = $false
            $attempt = 0
            while (-not $activated -and $attempt -lt 3) {
                $attempt += 1
                Invoke-PrimaryNavigationKey -WindowHandle $WindowHandle -ButtonLabel $target.Label -Key $key
                $activated = Wait-PrimaryNavigationState -WindowHandle $WindowHandle -PageLabel $target.Label -ButtonLabel $target.Label -RequireFocus -QuietTimeout:($attempt -lt 3) -TimeoutMilliseconds 1500
            }
            if (-not $activated) {
                throw "Primary navigation $key did not activate '$($target.Page)' while preserving focus on '$($target.Label)'."
            }
            $cases.Add([pscustomobject]@{
                key = $key
                target = $target.Page
                sentinel = $sentinel.Page
                focused = $target.Label
                page_visible = $true
                attempts = $attempt
            }) | Out-Null
        }
    }
    return $cases
}

function Invoke-PipelineLogNativeWindowProbe {
    param([Parameter(Mandatory)][IntPtr]$MainWindowHandle)

    Invoke-PrimaryNavigationClick -WindowHandle $MainWindowHandle -ButtonLabel 'Launch'
    $launchReady = Wait-PrimaryNavigationState -WindowHandle $MainWindowHandle -PageLabel 'Launch' -ButtonLabel 'Launch' -QuietTimeout -TimeoutMilliseconds 1500
    for ($launchAttempt = 1; -not $launchReady -and $launchAttempt -le 3; $launchAttempt++) {
        Invoke-PrimaryNavigationKey -WindowHandle $MainWindowHandle -ButtonLabel 'Launch' -Key 'Enter'
        $launchReady = Wait-PrimaryNavigationState -WindowHandle $MainWindowHandle -PageLabel 'Launch' -ButtonLabel 'Launch' -QuietTimeout:($launchAttempt -lt 3) -TimeoutMilliseconds 1500
    }
    if (-not $launchReady) {
        throw "UI Automation could not establish Launch before opening the native Pipeline Log window."
    }
    $mainRoot = Get-UiAutomationRoot -WindowHandle $MainWindowHandle
    $openButton = Find-UiAutomationButton -Root $mainRoot -Name 'Open Log Window'
    if (-not $openButton) { throw "UI Automation could not find the native 'Open Log Window' control." }
    $invokePattern = $null
    if (-not $openButton.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$invokePattern)) {
        throw "Native 'Open Log Window' control does not expose UI Automation InvokePattern."
    }
    ([System.Windows.Automation.InvokePattern]$invokePattern).Invoke()

    $logWindow = Wait-UiAutomationWindow -Name 'Pipeline Log' -TimeoutMilliseconds 10000
    if (-not $logWindow) {
        $buttonHelpText = ''
        $buttonName = ''
        try {
            Invoke-PrimaryNavigationClick -WindowHandle $MainWindowHandle -ButtonLabel 'Launch'
            [void](Wait-PrimaryNavigationState -WindowHandle $MainWindowHandle -PageLabel 'Launch' -ButtonLabel 'Launch')
            $failedButton = Find-UiAutomationButton -Root (Get-UiAutomationRoot -WindowHandle $MainWindowHandle) -Name 'Open Log Window'
            if ($failedButton) {
                $buttonHelpText = [string]$failedButton.Current.HelpText
                $buttonName = [string]$failedButton.Current.Name
            }
        } catch { }
        $diagnosticRows = @(Get-UiAutomationRows -WindowHandle $MainWindowHandle -Limit 1000 | Where-Object {
            $_.Name -match '(?i)pipeline|log|diagnostic|failed|opened|unavailable|blocked'
        } | Select-Object -First 80)
        throw "The native Pipeline Log window did not appear after its Tauri command was invoked. button_name=$buttonName button_help=$buttonHelpText main_window_diagnostics=$($diagnosticRows | ConvertTo-Json -Compress)"
    }
    $requiredControls = @('Follow', 'Pipeline Log display mode', 'Refresh Now')
    $observedControls = @()
    $controlDeadline = (Get-Date).AddSeconds(10)
    do {
        $logWindow = Find-UiAutomationWindow -Name 'Pipeline Log'
        if (-not $logWindow) { throw "Native Pipeline Log window closed before its controls became ready." }
        $observedControls = @($requiredControls | Where-Object {
            $condition = New-Object System.Windows.Automation.PropertyCondition(
                [System.Windows.Automation.AutomationElement]::NameProperty,
                $_
            )
            $null -ne $logWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
        })
        if ($observedControls.Count -eq $requiredControls.Count) { break }
        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $controlDeadline)
    $contentAccessibility = 'passed'
    $contentAccessibilityBlocker = ''
    if ($observedControls.Count -ne $requiredControls.Count) {
        $logWindowHandle = [IntPtr]$logWindow.Current.NativeWindowHandle
        $logDiagnostics = if ($logWindowHandle -ne [IntPtr]::Zero) {
            @(Get-UiAutomationRows -WindowHandle $logWindowHandle -Limit 220)
        } else {
            @()
        }
        $missingControls = @($requiredControls | Where-Object { $observedControls -notcontains $_ })
        $contentAccessibility = 'blocked'
        $contentAccessibilityBlocker = "Secondary WebView UI Automation did not expose: $($missingControls -join ', '). diagnostics=$($logDiagnostics | ConvertTo-Json -Compress)"
        Write-Warning $contentAccessibilityBlocker
    }

    $windowPattern = $null
    if (-not $logWindow.TryGetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern, [ref]$windowPattern)) {
        throw "Native Pipeline Log window does not expose UI Automation WindowPattern for safe close."
    }
    $uiAutomationLogHandle = [IntPtr]$logWindow.Current.NativeWindowHandle
    if ($uiAutomationLogHandle -eq [IntPtr]::Zero) {
        throw "Native Pipeline Log window did not expose a native window handle for close verification."
    }
    $nativeLogWindowHandle = Get-NativeRootWindowHandle -WindowHandle $uiAutomationLogHandle
    if ($nativeLogWindowHandle -eq [IntPtr]::Zero -or $nativeLogWindowHandle -eq $MainWindowHandle) {
        throw "Native Pipeline Log root window handle could not be isolated from the main window."
    }
    if (-not (Request-NativeWindowClose -WindowHandle $nativeLogWindowHandle)) {
        throw "Native Pipeline Log close request could not be posted."
    }
    $closeDeadline = (Get-Date).AddSeconds(10)
    do {
        if (
            -not (Test-NativeWindowHandle -WindowHandle $nativeLogWindowHandle) -or
            -not (Test-NativeWindowVisible -WindowHandle $nativeLogWindowHandle)
        ) { break }
        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $closeDeadline)
    if (
        (Test-NativeWindowHandle -WindowHandle $nativeLogWindowHandle) -and
        (Test-NativeWindowVisible -WindowHandle $nativeLogWindowHandle)
    ) {
        $closeOutcome = 'blocked-unverified-visible'
        $closeBlocker = 'The native close request was posted, but UI Automation and Win32 visibility still reported the secondary window as visible.'
        Write-Warning $closeBlocker
    } else {
        $closeOutcome = if (Test-NativeWindowHandle -WindowHandle $nativeLogWindowHandle) {
            'hidden'
        } else {
            'destroyed'
        }
        $closeBlocker = ''
    }
    return [pscustomobject]@{
        command = 'open_pipeline_log_window'
        title = 'Pipeline Log'
        controls = $observedControls
        expected_controls = $requiredControls
        content_accessibility = $contentAccessibility
        content_accessibility_blocker = $contentAccessibilityBlocker
        close_outcome = $closeOutcome
        close_blocker = $closeBlocker
        close_requested = $true
        closed = $closeOutcome -in @('hidden', 'destroyed')
    }
}

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$shellRoot = [System.IO.Path]::GetFullPath($scriptRoot)
$node = Resolve-ToolPath node
$npm = Resolve-ToolPath npm
$cargo = Resolve-ToolPath cargo
$vsDevCmd = Resolve-VsDevCmd
foreach ($tool in @(
    @{ Name = 'node'; Path = $node },
    @{ Name = 'npm'; Path = $npm },
    @{ Name = 'cargo'; Path = $cargo },
    @{ Name = 'VsDevCmd.bat'; Path = $vsDevCmd }
)) {
    if (-not $tool.Path) {
        throw "$($tool.Name) was not found. Run Test-TauriShell-Prereqs.ps1 -RequireToolchain -RequireBuildTools first."
    }
}

$baselineBackendIds = @(Get-LocalApiBackendProcesses | ForEach-Object { [int]$_.ProcessId })
$baselineShellIds = @(Get-TauriShellProcesses | ForEach-Object { [int]$_.Id })
$expectedWebView2Folder = ''
if ($ExpectedWebView2UserDataFolder) {
    $expectedWebView2Folder = [System.IO.Path]::GetFullPath($ExpectedWebView2UserDataFolder).TrimEnd('\', '/')
    $configuredWebView2Folder = if ($env:WEBVIEW2_USER_DATA_FOLDER) {
        [System.IO.Path]::GetFullPath($env:WEBVIEW2_USER_DATA_FOLDER).TrimEnd('\', '/')
    } else {
        ''
    }
    if (-not [string]::Equals($configuredWebView2Folder, $expectedWebView2Folder, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "WEBVIEW2_USER_DATA_FOLDER must equal the expected isolated folder before the probe launches. expected=$expectedWebView2Folder configured=$configuredWebView2Folder"
    }
}
$logRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'mediapipeline-tauri-shell-uia-probe'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$stdoutLog = Join-Path $logRoot "tauri_uia_$stamp.stdout.log"
$stderrLog = Join-Path $logRoot "tauri_uia_$stamp.stderr.log"

$nodeDir = Split-Path -Parent $node
$cargoDir = Split-Path -Parent $cargo
$cmdLine = 'call "' + $vsDevCmd + '" -arch=x64 -host_arch=x64 >nul && set "PATH=' + $nodeDir + ';' + $cargoDir + ';%PATH%" && set "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--force-renderer-accessibility" && npm run dev'

Write-Host "Launching Tauri dev shell from $shellRoot"
Write-Host "Logs: $stdoutLog"
$devProcess = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/s', '/c', $cmdLine) -WorkingDirectory $shellRoot -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -WindowStyle Hidden -PassThru
$newBackendIds = @()
$newShellIds = @()
$newWebView2Ids = @()
$verifiedWebView2Folder = ''
$visibleWindowProcess = $null
$mainWindowHandle = [IntPtr]::Zero
try {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($devProcess.HasExited) {
            throw "Tauri dev process exited before the window appeared. Exit=$($devProcess.ExitCode). stderr=$(Get-LogTail -Path $stderrLog)"
        }
        $shellProcesses = @(Get-TauriShellProcesses | Where-Object { $baselineShellIds -notcontains [int]$_.Id })
        $newShellIds = @($shellProcesses | ForEach-Object { [int]$_.Id })
        $visibleWindowProcess = $shellProcesses |
            Where-Object { $_.MainWindowTitle -eq $WindowTitle } |
            Select-Object -First 1
        $backendProcesses = @(Get-LocalApiBackendProcesses)
        $newBackendIds = @($backendProcesses | Where-Object { $baselineBackendIds -notcontains [int]$_.ProcessId } | ForEach-Object { [int]$_.ProcessId })
        if ($visibleWindowProcess -and $newBackendIds.Count -gt 0) { break }
        Start-Sleep -Milliseconds 500
    }

    if (-not $visibleWindowProcess) {
        throw "Tauri window '$WindowTitle' was not detected within $TimeoutSeconds seconds. stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }
    $mainWindowHandle = [IntPtr]$visibleWindowProcess.MainWindowHandle

    Write-Host "Detected Tauri window PID $($visibleWindowProcess.Id), backend PID(s): $($newBackendIds -join ', ')"
    if ($expectedWebView2Folder) {
        $webViewDeadline = (Get-Date).AddSeconds(10)
        $webViewRoots = @()
        do {
            $webViewRoots = @(Get-WebView2RootProcesses -ShellProcessIds $newShellIds)
            if ($webViewRoots.Count -gt 0) { break }
            Start-Sleep -Milliseconds 100
        } while ((Get-Date) -lt $webViewDeadline)
        if ($webViewRoots.Count -eq 0) {
            throw "WebView2 root process was not found for Tauri shell PID(s): $($newShellIds -join ', ')."
        }
        $newWebView2Ids = @($webViewRoots | ForEach-Object { [int]$_.ProcessId })
        $observedFolders = @($webViewRoots | ForEach-Object {
            Get-WebView2UserDataFolder -CommandLine ([string]$_.CommandLine)
        })
        $expectedWebView2Prefix = $expectedWebView2Folder + [System.IO.Path]::DirectorySeparatorChar
        $unexpectedFolders = @($observedFolders | Where-Object {
            -not $_ -or (
                -not [string]::Equals($_, $expectedWebView2Folder, [System.StringComparison]::OrdinalIgnoreCase) -and
                -not $_.StartsWith($expectedWebView2Prefix, [System.StringComparison]::OrdinalIgnoreCase)
            )
        })
        if ($unexpectedFolders.Count -gt 0) {
            throw "WebView2 did not use a user-data folder under the expected isolated root. expected_root=$expectedWebView2Folder observed=$($observedFolders -join ', ')"
        }
        $verifiedWebView2Folder = @($observedFolders | Select-Object -Unique) -join ', '
        Write-Host "Verified isolated WebView2 user-data folder: $verifiedWebView2Folder"
    }
    $keyboardNavigation = if ($SkipPrimaryNavigationKeyboardProbe) {
        @()
    } else {
        @(Invoke-PrimaryNavigationKeyboardProbe -WindowHandle $mainWindowHandle)
    }
    $pipelineLogWindow = Invoke-PipelineLogNativeWindowProbe -MainWindowHandle $mainWindowHandle
    $rows = @(Get-UiAutomationRows -WindowHandle $mainWindowHandle -Limit $MaxElements)
    $interesting = @($rows | Where-Object {
        $_.AutomationId -or
        $_.Name -match 'Launch|Start Pipeline|Single File|Mode|Schedule|Dashboard|Sample Validation|Append Validation'
    })
    [pscustomobject]@{
        ok = $true
        shell_pid = [int]$visibleWindowProcess.Id
        backend_pids = $newBackendIds
        stdout_log = $stdoutLog
        stderr_log = $stderrLog
        webview2_user_data_folder = $verifiedWebView2Folder
        webview2_root_pids = $newWebView2Ids
        inspected_count = $rows.Count
        interesting = $interesting
        keyboard_navigation = $keyboardNavigation
        pipeline_log_window = $pipelineLogWindow
    } | ConvertTo-Json -Depth 6

    for ($closeAttempt = 1; $closeAttempt -le 3; $closeAttempt++) {
        $visibleWindowProcess.Refresh()
        if ($visibleWindowProcess.HasExited) { break }
        if (-not $visibleWindowProcess.CloseMainWindow()) {
            Write-Warning "Tauri main-window close attempt $closeAttempt was not accepted by PID $($visibleWindowProcess.Id)."
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $devProcess.WaitForExit($CloseTimeoutSeconds * 1000)) {
        Write-Warning "Tauri dev process did not exit within $CloseTimeoutSeconds seconds; forcing the isolated probe tree to stop."
        Stop-ProcessTree -Process $devProcess
        foreach ($processId in @($newShellIds + $newBackendIds + $newWebView2Ids | Select-Object -Unique)) {
            Stop-ProcessIdTree -ProcessId $processId
        }
    }
    $trackedProcessIds = @($newShellIds + $newBackendIds + $newWebView2Ids | Select-Object -Unique)
    $remainingProcessIds = @(Wait-ProcessIdsGone -ProcessIds $trackedProcessIds -TimeoutSeconds $CloseTimeoutSeconds)
    if ($remainingProcessIds.Count -gt 0) {
        foreach ($processId in $remainingProcessIds) {
            Stop-ProcessIdTree -ProcessId $processId
        }
        $remainingProcessIds = @(Wait-ProcessIdsGone -ProcessIds $remainingProcessIds -TimeoutSeconds 5)
    }
    if ($remainingProcessIds.Count -gt 0) {
        throw "Probe cleanup left tracked processes running after forced cleanup. process_ids=$($remainingProcessIds -join ', ')"
    }
} finally {
    if ($devProcess -and -not $devProcess.HasExited) {
        Stop-ProcessTree -Process $devProcess
    }
    foreach ($shellPid in $newShellIds) {
        Stop-ProcessIdTree -ProcessId $shellPid
    }
    foreach ($backendPid in $newBackendIds) {
        Stop-ProcessIdTree -ProcessId $backendPid
    }
    foreach ($webView2Pid in $newWebView2Ids) {
        Stop-ProcessIdTree -ProcessId $webView2Pid
    }
}
