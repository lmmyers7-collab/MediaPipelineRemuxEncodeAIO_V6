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

Write-Host "Encode flag policy checks passed. Snapshot count: $(@($snapshotCases).Count)."
