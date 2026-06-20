param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSScriptRoot."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\media_constants.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\shared\failure_codes.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\config\choice_registry.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\config\default_values.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\encoder_descriptors.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\encode_policy.ps1')

function Assert-Equal {
    param(
        [Parameter(Mandatory)] $Actual,
        [Parameter(Mandatory)] $Expected,
        [Parameter(Mandatory)] [string] $Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory)] [bool] $Condition,
        [Parameter(Mandatory)] [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Throws {
    param(
        [Parameter(Mandatory)] [scriptblock] $ScriptBlock,
        [Parameter(Mandatory)] [string] $Message
    )
    $didThrow = $false
    try {
        & $ScriptBlock
    } catch {
        $didThrow = $true
    }
    if (-not $didThrow) { throw $Message }
}

function New-PlanFromCase {
    param(
        [hashtable] $Overrides = @{}
    )

    $base = @{
        UseCpuFallback       = $false
        UseSafeHardwareRetry = $false
        IsTV                 = $false
        IsHDR                = $false
        InputPath            = 'in.mkv'
        ExtraInputs          = @()
        GlobalTitle          = 'T'
        AudioArgs            = @()
        SubtitleMapArgs      = @()
        VideoFilterArgs      = @()
        OutputPath           = 'out.mkv'
        VideoCodec           = 'hevc_nvenc'
        VideoPreset          = 'p7'
        VideoQuality         = 22
        ExtraVideoFlags      = @()
        FallbackCpuQuality   = 20
        EncodeLadder         = 'auto'
        CpuPreset            = 'medium'
        CpuMaxThreads        = 0
        Hdr10MasterDisplay   = ''
        Hdr10MaxCll          = ''
    }
    foreach ($key in $Overrides.Keys) {
        $base[$key] = $Overrides[$key]
    }
    return (New-EncodeAttemptPlan @base)
}

$hdr10MasterDisplay = 'G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)'
$hdr10MaxCll = '1000,400'

$snapshotCases = @(
    [pscustomobject]@{
        Name = 'primary sdr mkv auto movie'
        Params = @{}
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-profile:v|main|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'primary'
        Route = 'encode'
        Label = 'ENCODE'
        ProgressStage = 'encode'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'primary sdr mp4 auto movie'
        Params = @{ OutputPath = 'out.mp4' }
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|-1|-map_metadata|-1|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-profile:v|main|-f|mp4|-movflags|+faststart|-max_muxing_queue_size|1024|-y|out.mp4'
        Attempt = 'primary'
        Route = 'encode'
        Label = 'ENCODE'
        ProgressStage = 'encode'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'primary sdr mkv tv-balanced'
        Params = @{ EncodeLadder = 'tv_balanced' }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|23|-maxrate|90M|-bufsize|180M|-profile:v|main|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'primary'
        Route = 'encode'
        Label = 'ENCODE'
        ProgressStage = 'encode'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'tv_balanced'
    },
    [pscustomobject]@{
        Name = 'primary sdr mkv plex-compat'
        Params = @{ EncodeLadder = 'plex_compat' }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|23|-maxrate|80M|-bufsize|160M|-rc|vbr|-spatial-aq|1|-aq-strength|6|-bf|2|-profile:v|main|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'primary'
        Route = 'encode'
        Label = 'ENCODE'
        ProgressStage = 'encode'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'plex_compat'
    },
    [pscustomobject]@{
        Name = 'primary sdr mkv auto tv'
        Params = @{ IsTV = $true }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|23|-maxrate|90M|-bufsize|180M|-profile:v|main|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'primary'
        Route = 'encode'
        Label = 'ENCODE'
        ProgressStage = 'encode'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'tv_balanced'
    },
    [pscustomobject]@{
        Name = 'primary hdr no metadata mkv'
        Params = @{ IsHDR = $true }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-profile:v|main10|-pix_fmt|p010le|-color_primaries|bt2020|-color_trc|smpte2084|-colorspace|bt2020nc|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'primary'
        Route = 'encode'
        Label = 'ENCODE'
        ProgressStage = 'encode'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'primary hdr with metadata mkv'
        Params = @{ IsHDR = $true; Hdr10MasterDisplay = $hdr10MasterDisplay; Hdr10MaxCll = $hdr10MaxCll }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-profile:v|main10|-pix_fmt|p010le|-color_primaries|bt2020|-color_trc|smpte2084|-colorspace|bt2020nc|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'primary'
        Route = 'encode'
        Label = 'ENCODE'
        ProgressStage = 'encode'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'primary hdr with metadata mp4 plex-compat'
        Params = @{ IsHDR = $true; OutputPath = 'out.mp4'; EncodeLadder = 'plex_compat'; Hdr10MasterDisplay = $hdr10MasterDisplay; Hdr10MaxCll = $hdr10MaxCll }
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|-1|-map_metadata|-1|-c:v|hevc_nvenc|-preset|p7|-cq|23|-maxrate|80M|-bufsize|160M|-rc|vbr|-spatial-aq|1|-aq-strength|6|-bf|2|-profile:v|main10|-pix_fmt|p010le|-color_primaries|bt2020|-color_trc|smpte2084|-colorspace|bt2020nc|-f|mp4|-movflags|+faststart|-max_muxing_queue_size|1024|-y|out.mp4'
        Attempt = 'primary'
        Route = 'encode'
        Label = 'ENCODE'
        ProgressStage = 'encode'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'plex_compat'
    },
    [pscustomobject]@{
        Name = 'safe sdr mkv auto'
        Params = @{ UseSafeHardwareRetry = $true }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-rc|vbr|-spatial-aq|1|-aq-strength|6|-bf|2|-profile:v|main|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'hardware_safe_retry'
        Route = 'encode'
        Label = 'ENCODE-SAFE'
        ProgressStage = 'encode_safe'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'safe sdr mp4 tv-balanced'
        Params = @{ UseSafeHardwareRetry = $true; OutputPath = 'out.mp4'; EncodeLadder = 'tv_balanced' }
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|-1|-map_metadata|-1|-c:v|hevc_nvenc|-preset|p7|-cq|23|-maxrate|90M|-bufsize|180M|-rc|vbr|-spatial-aq|1|-aq-strength|6|-bf|2|-profile:v|main|-f|mp4|-movflags|+faststart|-max_muxing_queue_size|1024|-y|out.mp4'
        Attempt = 'hardware_safe_retry'
        Route = 'encode'
        Label = 'ENCODE-SAFE'
        ProgressStage = 'encode_safe'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'tv_balanced'
    },
    [pscustomobject]@{
        Name = 'safe hdr with metadata mkv plex-compat'
        Params = @{ UseSafeHardwareRetry = $true; IsHDR = $true; EncodeLadder = 'plex_compat'; Hdr10MasterDisplay = $hdr10MasterDisplay; Hdr10MaxCll = $hdr10MaxCll }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|23|-maxrate|80M|-bufsize|160M|-rc|vbr|-spatial-aq|1|-aq-strength|6|-bf|2|-profile:v|main10|-pix_fmt|p010le|-color_primaries|bt2020|-color_trc|smpte2084|-colorspace|bt2020nc|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'hardware_safe_retry'
        Route = 'encode'
        Label = 'ENCODE-SAFE'
        ProgressStage = 'encode_safe'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'plex_compat'
    },
    [pscustomobject]@{
        Name = 'cpu sdr mkv auto threads0'
        Params = @{ UseCpuFallback = $true }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-x265-params|log-level=error|-profile:v|main|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'cpu_fallback'
        Route = 'encode-cpu-fallback'
        Label = 'ENCODE-CPU'
        ProgressStage = 'encode_cpu'
        EncoderKind = 'cpu'
        SelectedEncoder = 'libx265'
        CpuPreset = 'medium'
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'cpu sdr mkv auto threads8'
        Params = @{ UseCpuFallback = $true; CpuMaxThreads = 8 }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-threads|8|-x265-params|log-level=error:pools=8:frame-threads=2|-profile:v|main|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'cpu_fallback'
        Route = 'encode-cpu-fallback'
        Label = 'ENCODE-CPU'
        ProgressStage = 'encode_cpu'
        EncoderKind = 'cpu'
        SelectedEncoder = 'libx265'
        CpuPreset = 'medium'
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'cpu sdr mp4 tv-balanced threads8'
        Params = @{ UseCpuFallback = $true; OutputPath = 'out.mp4'; EncodeLadder = 'tv_balanced'; CpuMaxThreads = 8 }
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|-1|-map_metadata|-1|-c:v|libx265|-preset|medium|-crf|21|-threads|8|-x265-params|log-level=error:pools=8:frame-threads=2|-profile:v|main|-f|mp4|-movflags|+faststart|-max_muxing_queue_size|1024|-y|out.mp4'
        Attempt = 'cpu_fallback'
        Route = 'encode-cpu-fallback'
        Label = 'ENCODE-CPU'
        ProgressStage = 'encode_cpu'
        EncoderKind = 'cpu'
        SelectedEncoder = 'libx265'
        CpuPreset = 'medium'
        EncodeLadder = 'tv_balanced'
    },
    [pscustomobject]@{
        Name = 'cpu sdr mkv movie-archive threads0'
        Params = @{ UseCpuFallback = $true; EncodeLadder = 'movie_archive' }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|19|-x265-params|log-level=error|-profile:v|main|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'cpu_fallback'
        Route = 'encode-cpu-fallback'
        Label = 'ENCODE-CPU'
        ProgressStage = 'encode_cpu'
        EncoderKind = 'cpu'
        SelectedEncoder = 'libx265'
        CpuPreset = 'medium'
        EncodeLadder = 'movie_archive'
    },
    [pscustomobject]@{
        Name = 'cpu sdr mkv plex-compat threads0'
        Params = @{ UseCpuFallback = $true; EncodeLadder = 'plex_compat' }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|21|-x265-params|log-level=error|-profile:v|main|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'cpu_fallback'
        Route = 'encode-cpu-fallback'
        Label = 'ENCODE-CPU'
        ProgressStage = 'encode_cpu'
        EncoderKind = 'cpu'
        SelectedEncoder = 'libx265'
        CpuPreset = 'medium'
        EncodeLadder = 'plex_compat'
    },
    [pscustomobject]@{
        Name = 'cpu hdr no metadata mkv'
        Params = @{ UseCpuFallback = $true; IsHDR = $true }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-x265-params|log-level=error:hdr10=1:hdr10-opt=1:repeat-headers=1:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc|-profile:v|main10|-pix_fmt|p010le|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'cpu_fallback'
        Route = 'encode-cpu-fallback'
        Label = 'ENCODE-CPU'
        ProgressStage = 'encode_cpu'
        EncoderKind = 'cpu'
        SelectedEncoder = 'libx265'
        CpuPreset = 'medium'
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'cpu hdr with metadata mkv'
        Params = @{ UseCpuFallback = $true; IsHDR = $true; Hdr10MasterDisplay = $hdr10MasterDisplay; Hdr10MaxCll = $hdr10MaxCll }
        Expected = '-i|in.mkv|-map|0:V|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-x265-params|log-level=error:hdr10=1:hdr10-opt=1:repeat-headers=1:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1):max-cll=1000,400|-profile:v|main10|-pix_fmt|p010le|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'cpu_fallback'
        Route = 'encode-cpu-fallback'
        Label = 'ENCODE-CPU'
        ProgressStage = 'encode_cpu'
        EncoderKind = 'cpu'
        SelectedEncoder = 'libx265'
        CpuPreset = 'medium'
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'cpu hdr with metadata mp4 plex-compat threads8'
        Params = @{ UseCpuFallback = $true; IsHDR = $true; OutputPath = 'out.mp4'; EncodeLadder = 'plex_compat'; CpuMaxThreads = 8; Hdr10MasterDisplay = $hdr10MasterDisplay; Hdr10MaxCll = $hdr10MaxCll }
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|-1|-map_metadata|-1|-c:v|libx265|-preset|medium|-crf|21|-threads|8|-x265-params|log-level=error:pools=8:frame-threads=2:hdr10=1:hdr10-opt=1:repeat-headers=1:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1):max-cll=1000,400|-profile:v|main10|-pix_fmt|p010le|-f|mp4|-movflags|+faststart|-max_muxing_queue_size|1024|-y|out.mp4'
        Attempt = 'cpu_fallback'
        Route = 'encode-cpu-fallback'
        Label = 'ENCODE-CPU'
        ProgressStage = 'encode_cpu'
        EncoderKind = 'cpu'
        SelectedEncoder = 'libx265'
        CpuPreset = 'medium'
        EncodeLadder = 'plex_compat'
    },
    [pscustomobject]@{
        Name = 'primary complex segment ordering mkv'
        Params = @{
            ExtraInputs = @('-i','subs.srt')
            VideoFilterArgs = @('-map','0:V','-vf','scale=1920:-2')
            AudioArgs = @('-map','0:a:0','-c:a:0','copy')
            SubtitleMapArgs = @('-map','1:s:0','-c:s:0','srt')
            ExtraVideoFlags = @('-gpu','0','-rc-lookahead','32')
        }
        Expected = '-i|in.mkv|-i|subs.srt|-map|0:V|-vf|scale=1920:-2|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-gpu|0|-rc-lookahead|32|-profile:v|main|-map|0:a:0|-c:a:0|copy|-map|1:s:0|-c:s:0|srt|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'primary'
        Route = 'encode'
        Label = 'ENCODE'
        ProgressStage = 'encode'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'safe complex segment ordering mp4'
        Params = @{
            UseSafeHardwareRetry = $true
            OutputPath = 'out.mp4'
            ExtraInputs = @('-i','subs.srt')
            VideoFilterArgs = @('-map','0:V','-vf','scale=1920:-2')
            AudioArgs = @('-map','0:a:0','-c:a:0','copy')
            SubtitleMapArgs = @('-map','1:s:0','-c:s:0','srt')
            ExtraVideoFlags = @('-gpu','0','-rc-lookahead','32')
        }
        Expected = '-i|in.mkv|-i|subs.srt|-map|0:V|-vf|scale=1920:-2|-map_chapters|-1|-map_metadata|-1|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-rc|vbr|-spatial-aq|1|-aq-strength|6|-bf|2|-profile:v|main|-map|0:a:0|-c:a:0|copy|-map|1:s:0|-c:s:0|srt|-f|mp4|-movflags|+faststart|-max_muxing_queue_size|1024|-y|out.mp4'
        Attempt = 'hardware_safe_retry'
        Route = 'encode'
        Label = 'ENCODE-SAFE'
        ProgressStage = 'encode_safe'
        EncoderKind = 'nvenc'
        SelectedEncoder = 'hevc_nvenc'
        CpuPreset = ''
        EncodeLadder = 'movie_balanced'
    },
    [pscustomobject]@{
        Name = 'cpu complex segment ordering mkv threads8'
        Params = @{
            UseCpuFallback = $true
            CpuMaxThreads = 8
            ExtraInputs = @('-i','subs.srt')
            VideoFilterArgs = @('-map','0:V','-vf','scale=1920:-2')
            AudioArgs = @('-map','0:a:0','-c:a:0','copy')
            SubtitleMapArgs = @('-map','1:s:0','-c:s:0','srt')
        }
        Expected = '-i|in.mkv|-i|subs.srt|-map|0:V|-vf|scale=1920:-2|-map|0:t?|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-threads|8|-x265-params|log-level=error:pools=8:frame-threads=2|-profile:v|main|-map|0:a:0|-c:a:0|copy|-map|1:s:0|-c:s:0|srt|-c:t|copy|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
        Attempt = 'cpu_fallback'
        Route = 'encode-cpu-fallback'
        Label = 'ENCODE-CPU'
        ProgressStage = 'encode_cpu'
        EncoderKind = 'cpu'
        SelectedEncoder = 'libx265'
        CpuPreset = 'medium'
        EncodeLadder = 'movie_balanced'
    }
)

foreach ($case in $snapshotCases) {
    $plan = New-PlanFromCase -Overrides $case.Params
    $joined = (@($plan.ArgumentList) -join '|')
    Assert-Equal $joined ([string]$case.Expected) "Argument snapshot mismatch for $($case.Name)."
    Assert-Equal ([string]$plan.Attempt) ([string]$case.Attempt) "Attempt mismatch for $($case.Name)."
    Assert-Equal ([string]$plan.Route) ([string]$case.Route) "Route mismatch for $($case.Name)."
    Assert-Equal ([string]$plan.Label) ([string]$case.Label) "Label mismatch for $($case.Name)."
    Assert-Equal ([string]$plan.ProgressStage) ([string]$case.ProgressStage) "ProgressStage mismatch for $($case.Name)."
    Assert-Equal ([string]$plan.EncoderKind) ([string]$case.EncoderKind) "EncoderKind mismatch for $($case.Name)."
    Assert-Equal ([string]$plan.SelectedEncoder) ([string]$case.SelectedEncoder) "SelectedEncoder mismatch for $($case.Name)."
    Assert-Equal ([string]$plan.CpuPreset) ([string]$case.CpuPreset) "CpuPreset mismatch for $($case.Name)."
    Assert-Equal ([string]$plan.EncodeLadder) ([string]$case.EncodeLadder) "EncodeLadder mismatch for $($case.Name)."
}

$metadataAttempts = @($snapshotCases | Select-Object -ExpandProperty Attempt -Unique)
Assert-True ($metadataAttempts -contains 'primary') 'Snapshot set must cover primary attempt metadata.'
Assert-True ($metadataAttempts -contains 'hardware_safe_retry') 'Snapshot set must cover hardware safe-retry attempt metadata.'
Assert-True ($metadataAttempts -contains 'cpu_fallback') 'Snapshot set must cover CPU fallback attempt metadata.'

$hevcNvencDescriptor = Get-MediaEncoderDescriptor -Family 'hevc' -Backend 'nvenc'
Assert-True ($null -ne $hevcNvencDescriptor) 'HEVC/NVENC descriptor must exist for the behavior-identical descriptor scaffold.'
Assert-Equal ([string]$hevcNvencDescriptor.EncoderName) 'hevc_nvenc' 'HEVC/NVENC descriptor encoder mismatch.'
Assert-Equal ([string]$hevcNvencDescriptor.RateControlKind) 'nvenc_cq' 'HEVC/NVENC descriptor rate-control mismatch.'
Assert-Equal ([bool]$hevcNvencDescriptor.UsesVbv) $true 'HEVC/NVENC descriptor must preserve VBV emission.'

$hevcCpuDescriptor = Get-MediaEncoderDescriptor -Family 'hevc' -Backend 'cpu'
Assert-True ($null -ne $hevcCpuDescriptor) 'HEVC/CPU descriptor must exist for libx265 fallback.'
Assert-Equal ([string]$hevcCpuDescriptor.EncoderName) 'libx265' 'HEVC/CPU descriptor encoder mismatch.'
Assert-Equal ([string]$hevcCpuDescriptor.RateControlKind) 'x265_crf' 'HEVC/CPU descriptor rate-control mismatch.'
Assert-Equal ([bool]$hevcCpuDescriptor.UsesVbv) $false 'HEVC/CPU descriptor must preserve no-VBV CRF behavior.'

$h264NvencDescriptor = Get-MediaEncoderDescriptor -Family 'h264' -Backend 'nvenc'
Assert-True ($null -ne $h264NvencDescriptor) 'Dormant H.264/NVENC descriptor must exist before activation work.'
Assert-Equal ([string]$h264NvencDescriptor.EncoderName) 'h264_nvenc' 'H.264/NVENC descriptor encoder mismatch.'
Assert-Equal ([string]$h264NvencDescriptor.RateControlKind) 'nvenc_cq' 'H.264/NVENC descriptor rate-control mismatch.'
Assert-Equal ([bool]$h264NvencDescriptor.SupportsHdr10Metadata) $false 'H.264/NVENC descriptor must not claim HDR10 metadata support.'
Assert-True ($null -eq (Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'h264_nvenc' -UseCpuFallback:$false)) 'H.264/NVENC must keep the legacy branch until activation work.'

$h264NvencFlags = @(New-EncoderVideoFlags `
    -Descriptor $h264NvencDescriptor `
    -VideoCodec 'h264_nvenc' `
    -VideoPreset 'p7' `
    -VideoQuality 22)
Assert-Equal (@($h264NvencFlags) -join '|') '-c:v|h264_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-profile:v|high' 'Dormant H.264/NVENC descriptor flags mismatch.'
Assert-Throws { New-EncoderVideoFlags -Descriptor $h264NvencDescriptor -IsHDR:$true -VideoCodec 'h264_nvenc' -VideoPreset 'p7' -VideoQuality 22 | Out-Null } 'H.264/NVENC HDR use must fail closed until HDR preservation is proven.'

$h264CpuDescriptor = Get-MediaEncoderDescriptor -Family 'h264' -Backend 'cpu'
Assert-True ($null -ne $h264CpuDescriptor) 'Dormant H.264/CPU descriptor must exist before activation work.'
Assert-Equal ([string]$h264CpuDescriptor.EncoderName) 'libx264' 'H.264/CPU descriptor encoder mismatch.'
Assert-Equal ([string]$h264CpuDescriptor.RateControlKind) 'x264_crf' 'H.264/CPU descriptor rate-control mismatch.'
Assert-Equal ([bool]$h264CpuDescriptor.UsesVbv) $false 'H.264/CPU descriptor must use CRF without VBV.'
Assert-True ($null -eq (Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'libx264' -UseCpuFallback:$true)) 'H.264/CPU must keep the legacy CPU branch until activation work.'

$h264CpuFlags = @(New-EncoderVideoFlags `
    -Descriptor $h264CpuDescriptor `
    -VideoCodec 'libx264' `
    -VideoPreset 'p7' `
    -VideoQuality 22 `
    -FallbackCpuQuality 20 `
    -CpuPreset 'medium' `
    -CpuMaxThreads 8)
Assert-Equal (@($h264CpuFlags) -join '|') '-c:v|libx264|-preset|medium|-crf|20|-threads|8|-profile:v|high' 'Dormant H.264/CPU descriptor flags mismatch.'
Assert-Throws { New-EncoderVideoFlags -Descriptor $h264CpuDescriptor -IsHDR:$true -VideoCodec 'libx264' -VideoPreset 'p7' -VideoQuality 22 | Out-Null } 'H.264/CPU HDR use must fail closed until HDR preservation is proven.'

$av1NvencDescriptor = Get-MediaEncoderDescriptor -Family 'av1' -Backend 'nvenc'
Assert-True ($null -ne $av1NvencDescriptor) 'Dormant AV1/NVENC descriptor must exist before activation work.'
Assert-Equal ([string]$av1NvencDescriptor.EncoderName) 'av1_nvenc' 'AV1/NVENC descriptor encoder mismatch.'
Assert-Equal ([string]$av1NvencDescriptor.RateControlKind) 'nvenc_cq' 'AV1/NVENC descriptor rate-control mismatch.'
Assert-Equal ([bool]$av1NvencDescriptor.SupportsHdr10Metadata) $true 'AV1/NVENC descriptor should be able to carry HDR10 color metadata.'
Assert-True ($null -eq (Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'av1_nvenc' -UseCpuFallback:$false)) 'AV1/NVENC must keep the legacy branch until activation work.'

$av1NvencSdrFlags = @(New-EncoderVideoFlags `
    -Descriptor $av1NvencDescriptor `
    -VideoCodec 'av1_nvenc' `
    -VideoPreset 'p7' `
    -VideoQuality 22)
Assert-Equal (@($av1NvencSdrFlags) -join '|') '-c:v|av1_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M' 'Dormant AV1/NVENC SDR descriptor flags mismatch.'
Assert-True (-not (@($av1NvencSdrFlags) -contains '-profile:v')) 'AV1/NVENC must not inherit HEVC profile flags for SDR.'

$av1NvencHdrFlags = @(New-EncoderVideoFlags `
    -Descriptor $av1NvencDescriptor `
    -IsHDR:$true `
    -VideoCodec 'av1_nvenc' `
    -VideoPreset 'p7' `
    -VideoQuality 22)
Assert-Equal (@($av1NvencHdrFlags) -join '|') '-c:v|av1_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-pix_fmt|p010le|-color_primaries|bt2020|-color_trc|smpte2084|-colorspace|bt2020nc' 'Dormant AV1/NVENC HDR descriptor flags mismatch.'
Assert-True (-not (@($av1NvencHdrFlags) -contains '-profile:v')) 'AV1/NVENC HDR must omit HEVC-style main10 profile flags.'

$av1CpuDescriptor = Get-MediaEncoderDescriptor -Family 'av1' -Backend 'cpu'
Assert-True ($null -ne $av1CpuDescriptor) 'Dormant AV1/CPU descriptor must exist before activation work.'
Assert-Equal ([string]$av1CpuDescriptor.EncoderName) 'libaom-av1' 'AV1/CPU descriptor encoder mismatch.'
Assert-Equal ([string]$av1CpuDescriptor.RateControlKind) 'aom_crf' 'AV1/CPU descriptor rate-control mismatch.'
Assert-Equal ([bool]$av1CpuDescriptor.SupportsHdr10Metadata) $false 'libaom AV1 descriptor must not claim HDR10 metadata support.'
Assert-True ($null -eq (Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'libaom-av1' -UseCpuFallback:$true)) 'AV1/CPU must keep the legacy CPU branch until activation work.'

$av1CpuFlags = @(New-EncoderVideoFlags `
    -Descriptor $av1CpuDescriptor `
    -VideoCodec 'libaom-av1' `
    -VideoPreset 'p7' `
    -VideoQuality 22 `
    -FallbackCpuQuality 20 `
    -CpuMaxThreads 8)
Assert-Equal (@($av1CpuFlags) -join '|') '-c:v|libaom-av1|-crf|22|-b:v|0|-cpu-used|1|-threads|8' 'Dormant AV1/CPU descriptor flags mismatch.'
Assert-Throws { New-EncoderVideoFlags -Descriptor $av1CpuDescriptor -IsHDR:$true -VideoCodec 'libaom-av1' -VideoPreset 'p7' -VideoQuality 22 | Out-Null } 'AV1/CPU HDR use must fail closed until HDR preservation is proven.'

$qsvDescriptorCases = @(
    @{ Family = 'hevc'; Codec = 'hevc_qsv'; Preset = 'p7'; ExpectedPreset = 'veryslow'; Expected = '-c:v|hevc_qsv|-preset|veryslow|-global_quality|24' },
    @{ Family = 'h264'; Codec = 'h264_qsv'; Preset = 'p1'; ExpectedPreset = 'veryfast'; Expected = '-c:v|h264_qsv|-preset|veryfast|-global_quality|24' },
    @{ Family = 'av1';  Codec = 'av1_qsv';  Preset = 'p4'; ExpectedPreset = 'medium'; Expected = '-c:v|av1_qsv|-preset|medium|-global_quality|24' }
)
foreach ($case in $qsvDescriptorCases) {
    $descriptor = Get-MediaEncoderDescriptor -Family ([string]$case.Family) -Backend 'qsv'
    Assert-True ($null -ne $descriptor) "Dormant $($case.Family)/QSV descriptor must exist before activation work."
    Assert-Equal ([string]$descriptor.EncoderName) ([string]$case.Codec) "$($case.Family)/QSV descriptor encoder mismatch."
    Assert-Equal ([string]$descriptor.RateControlKind) 'qsv_global_quality' "$($case.Family)/QSV descriptor rate-control mismatch."
    Assert-Equal ([string]$descriptor.FailurePatternKind) 'qsv' "$($case.Family)/QSV descriptor failure pattern mismatch."
    Assert-Equal ([bool]$descriptor.SupportsHdr10Metadata) $false "$($case.Family)/QSV descriptor must stay HDR-blocked until real validation."
    Assert-Equal ([string]$descriptor.PresetMap[[string]$case.Preset]) ([string]$case.ExpectedPreset) "$($case.Family)/QSV preset map mismatch."
    Assert-True ($null -eq (Resolve-MediaEncoderDescriptorForFlags -VideoCodec ([string]$case.Codec) -UseCpuFallback:$false)) "$($case.Family)/QSV must keep the legacy branch until activation work."
    $flags = @(New-EncoderVideoFlags `
        -Descriptor $descriptor `
        -VideoCodec ([string]$case.Codec) `
        -VideoPreset ([string]$case.Preset) `
        -VideoQuality 22)
    Assert-Equal (@($flags) -join '|') ([string]$case.Expected) "Dormant $($case.Family)/QSV descriptor flags mismatch."
    Assert-Throws { New-EncoderVideoFlags -Descriptor $descriptor -IsHDR:$true -VideoCodec ([string]$case.Codec) -VideoPreset ([string]$case.Preset) -VideoQuality 22 | Out-Null } "$($case.Family)/QSV HDR use must fail closed until HDR preservation is proven."
}

$amfDescriptorCases = @(
    @{ Family = 'hevc'; Codec = 'hevc_amf'; Preset = 'p7'; ExpectedQuality = 'quality'; Expected = '-c:v|hevc_amf|-quality|quality|-rc|cqp|-qp_i|22|-qp_p|22' },
    @{ Family = 'h264'; Codec = 'h264_amf'; Preset = 'p1'; ExpectedQuality = 'speed'; Expected = '-c:v|h264_amf|-quality|speed|-rc|cqp|-qp_i|22|-qp_p|22' },
    @{ Family = 'av1';  Codec = 'av1_amf';  Preset = 'p4'; ExpectedQuality = 'balanced'; Expected = '-c:v|av1_amf|-quality|balanced|-rc|cqp|-qp_i|22|-qp_p|22' }
)
foreach ($case in $amfDescriptorCases) {
    $descriptor = Get-MediaEncoderDescriptor -Family ([string]$case.Family) -Backend 'amf'
    Assert-True ($null -ne $descriptor) "Dormant $($case.Family)/AMF descriptor must exist before activation work."
    Assert-Equal ([string]$descriptor.EncoderName) ([string]$case.Codec) "$($case.Family)/AMF descriptor encoder mismatch."
    Assert-Equal ([string]$descriptor.RateControlKind) 'amf_cqp' "$($case.Family)/AMF descriptor rate-control mismatch."
    Assert-Equal ([string]$descriptor.FailurePatternKind) 'amf' "$($case.Family)/AMF descriptor failure pattern mismatch."
    Assert-Equal ([bool]$descriptor.SupportsHdr10Metadata) $false "$($case.Family)/AMF descriptor must stay HDR-blocked until real validation."
    Assert-Equal ([string]$descriptor.PresetMap[[string]$case.Preset]) ([string]$case.ExpectedQuality) "$($case.Family)/AMF quality map mismatch."
    Assert-True ($null -eq (Resolve-MediaEncoderDescriptorForFlags -VideoCodec ([string]$case.Codec) -UseCpuFallback:$false)) "$($case.Family)/AMF must keep the legacy branch until activation work."
    $flags = @(New-EncoderVideoFlags `
        -Descriptor $descriptor `
        -VideoCodec ([string]$case.Codec) `
        -VideoPreset ([string]$case.Preset) `
        -VideoQuality 22)
    Assert-Equal (@($flags) -join '|') ([string]$case.Expected) "Dormant $($case.Family)/AMF descriptor flags mismatch."
    Assert-Throws { New-EncoderVideoFlags -Descriptor $descriptor -IsHDR:$true -VideoCodec ([string]$case.Codec) -VideoPreset ([string]$case.Preset) -VideoQuality 22 | Out-Null } "$($case.Family)/AMF HDR use must fail closed until HDR preservation is proven."
}

$retryCases = @(
    @{ Name = 'success does not retry'; Success = $true; StopRequested = $false; ForceCpu = $false; VideoCodec = 'hevc_nvenc'; ErrorText = 'No NVENC capable devices found'; Expected = $false },
    @{ Name = 'stop does not retry'; Success = $false; StopRequested = $true; ForceCpu = $false; VideoCodec = 'hevc_nvenc'; ErrorText = 'No NVENC capable devices found'; Expected = $false },
    @{ Name = 'force cpu retries'; Success = $false; StopRequested = $false; ForceCpu = $true; VideoCodec = 'libx265'; ErrorText = 'unrelated'; Expected = $true },
    @{ Name = 'nvenc stderr retries'; Success = $false; StopRequested = $false; ForceCpu = $false; VideoCodec = 'hevc_nvenc'; ErrorText = 'No NVENC capable devices found'; Expected = $true },
    @{ Name = 'amf stderr retries'; Success = $false; StopRequested = $false; ForceCpu = $false; VideoCodec = 'hevc_amf'; ErrorText = 'CreateComponent failed during encoder initialization failed'; Expected = $true },
    @{ Name = 'qsv stderr retries'; Success = $false; StopRequested = $false; ForceCpu = $false; VideoCodec = 'hevc_qsv'; ErrorText = 'MFX_ERR_DEVICE_FAILED while opening qsv device'; Expected = $true },
    @{ Name = 'garbage stderr does not retry'; Success = $false; StopRequested = $false; ForceCpu = $false; VideoCodec = 'hevc_nvenc'; ErrorText = 'plain ffmpeg filtergraph syntax failure'; Expected = $false }
)

foreach ($case in $retryCases) {
    $actual = Test-ShouldRetryEncodeWithCpuFallback `
        -Success:([bool]$case.Success) `
        -StopRequested:([bool]$case.StopRequested) `
        -ForceCpu:([bool]$case.ForceCpu) `
        -VideoCodec ([string]$case.VideoCodec) `
        -ErrorText ([string]$case.ErrorText)
    Assert-Equal ([bool]$actual) ([bool]$case.Expected) "Retry truth-table mismatch for $($case.Name)."
}

$encodeEntryText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\encode.ps1') -Raw
Assert-True ($encodeEntryText -match 'Acquire-CpuEncodeMutex -TimeoutSeconds \$script:FFmpegCpuEncodeTimeoutSeconds') 'CPU fallback must wait for the CPU mutex after zero-time acquisition fails.'
Assert-True ($encodeEntryText -match 'if \(-not \$cpuMutexLock\.Acquired\)') 'CPU fallback must re-check mutex acquisition after the timed wait.'
Assert-True ($encodeEntryText -match 'ENCODE_CPU_MUTEX_UNAVAILABLE') 'CPU fallback mutex timeout must register a distinct failure code.'
Assert-True ($encodeEntryText -match 'refusing to start overlapping CPU fallback') 'CPU fallback mutex timeout should log a fail-closed operator reason.'

Write-Host "Encode flag policy checks passed. Snapshot count: $(@($snapshotCases).Count)."
