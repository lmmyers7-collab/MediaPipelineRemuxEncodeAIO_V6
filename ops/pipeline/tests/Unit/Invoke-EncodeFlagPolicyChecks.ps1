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
        EncoderBackend       = 'auto'
        VideoPreset          = 'p7'
        VideoQuality         = 22
        ExtraVideoFlags      = @()
        FallbackCpuQuality   = 20
        EncodeLadder         = 'auto'
        CpuPreset            = 'medium'
        CpuMaxThreads        = 0
        Hdr10MasterDisplay   = ''
        Hdr10MaxCll          = ''
        DolbyVisionRpuPath   = ''
        DolbyVisionTargetProfile = ''
        Hdr10PlusJsonPath    = ''
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-profile:v|main|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|23|-maxrate|90M|-bufsize|180M|-profile:v|main|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|23|-maxrate|80M|-bufsize|160M|-rc|vbr|-spatial-aq|1|-aq-strength|6|-bf|2|-profile:v|main|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|23|-maxrate|90M|-bufsize|180M|-profile:v|main|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-profile:v|main10|-pix_fmt|p010le|-color_primaries|bt2020|-color_trc|smpte2084|-colorspace|bt2020nc|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-profile:v|main10|-pix_fmt|p010le|-color_primaries|bt2020|-color_trc|smpte2084|-colorspace|bt2020nc|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-rc|vbr|-spatial-aq|1|-aq-strength|6|-bf|2|-profile:v|main|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|23|-maxrate|80M|-bufsize|160M|-rc|vbr|-spatial-aq|1|-aq-strength|6|-bf|2|-profile:v|main10|-pix_fmt|p010le|-color_primaries|bt2020|-color_trc|smpte2084|-colorspace|bt2020nc|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-x265-params|log-level=error|-profile:v|main|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-threads|8|-x265-params|log-level=error:pools=8:frame-threads=2|-profile:v|main|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|19|-x265-params|log-level=error|-profile:v|main|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|21|-x265-params|log-level=error|-profile:v|main|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-x265-params|log-level=error:hdr10=1:hdr10-opt=1:repeat-headers=1:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc|-profile:v|main10|-pix_fmt|p010le|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-x265-params|log-level=error:hdr10=1:hdr10-opt=1:repeat-headers=1:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1):max-cll=1000,400|-profile:v|main10|-pix_fmt|p010le|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Name = 'cpu hdr dynamic hdr artifacts mkv'
        Params = @{ UseCpuFallback = $true; IsHDR = $true; Hdr10MasterDisplay = $hdr10MasterDisplay; Hdr10MaxCll = $hdr10MaxCll; DolbyVisionRpuPath = 'dynamic_hdr\rpu.bin'; DolbyVisionTargetProfile = '8.1'; Hdr10PlusJsonPath = 'dynamic_hdr\hdr10plus.json' }
        Expected = '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-dolbyvision|true|-x265-params|log-level=error:hdr10=1:hdr10-opt=1:repeat-headers=1:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1):max-cll=1000,400:dolby-vision-profile=8.1:vbv-maxrate=50000:vbv-bufsize=50000:dhdr10-info=dynamic_hdr\hdr10plus.json|-profile:v|main10|-pix_fmt|p010le|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Name = 'primary complex segment ordering mkv'
        Params = @{
            ExtraInputs = @('-i','subs.srt')
            VideoFilterArgs = @('-map','0:V','-vf','scale=1920:-2')
            AudioArgs = @('-map','0:a:0','-c:a:0','copy')
            SubtitleMapArgs = @('-map','1:s:0','-c:s:0','srt')
            ExtraVideoFlags = @('-gpu','0','-rc-lookahead','32')
        }
        Expected = '-i|in.mkv|-i|subs.srt|-map|0:V|-vf|scale=1920:-2|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|hevc_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-gpu|0|-rc-lookahead|32|-profile:v|main|-map|0:a:0|-c:a:0|copy|-map|1:s:0|-c:s:0|srt|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
        Expected = '-i|in.mkv|-i|subs.srt|-map|0:V|-vf|scale=1920:-2|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx265|-preset|medium|-crf|20|-threads|8|-x265-params|log-level=error:pools=8:frame-threads=2|-profile:v|main|-map|0:a:0|-c:a:0|copy|-map|1:s:0|-c:s:0|srt|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv'
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
    Assert-True ($null -ne $plan.DescriptorSelection) "Descriptor selection evidence missing for $($case.Name)."
    Assert-Equal ([bool]$plan.DescriptorSelection.Active) $true "HEVC descriptor selection should be active for $($case.Name)."
    Assert-Equal ([bool]$plan.DescriptorSelection.Resolved) $true "HEVC descriptor selection should resolve for $($case.Name)."
    Assert-Equal ([string]$plan.DescriptorSelection.Family) 'hevc' "Descriptor family mismatch for $($case.Name)."
    Assert-Equal ([string]$plan.DescriptorSelection.SelectedEncoder) ([string]$case.SelectedEncoder) "Descriptor selected encoder mismatch for $($case.Name)."
    $expectedDescriptorRole = if ([string]$case.Attempt -eq 'cpu_fallback') { 'cpu_fallback' } else { 'primary' }
    Assert-Equal ([string]$plan.DescriptorSelection.Role) $expectedDescriptorRole "Descriptor role mismatch for $($case.Name)."
    Assert-True (@($plan.DescriptorSelection.ResolutionTrace).Count -gt 0) "Descriptor selection trace missing for $($case.Name)."
}

$av1NvencPlan = New-PlanFromCase -Overrides @{ VideoCodec = 'av1_nvenc' }
Assert-Equal ([string]$av1NvencPlan.SelectedEncoder) 'av1_nvenc' 'AV1/NVENC primary plan should expose the descriptor encoder.'
Assert-Equal ([bool]$av1NvencPlan.DescriptorSelection.Resolved) $true 'AV1/NVENC descriptor selection should resolve.'
Assert-Equal ([bool]$av1NvencPlan.DescriptorSelection.Active) $true 'AV1/NVENC descriptor selection must claim active descriptor flag ownership.'
Assert-Equal ([string]$av1NvencPlan.DescriptorSelection.PrimaryEncoder) 'av1_nvenc' 'AV1/NVENC descriptor primary evidence mismatch.'
Assert-Equal ([string]$av1NvencPlan.DescriptorSelection.CpuFallbackEncoder) 'libaom-av1' 'AV1/NVENC descriptor fallback evidence mismatch.'
Assert-Equal ([string]$av1NvencPlan.DescriptorSelection.DescriptorBackend) 'nvenc' 'AV1/NVENC descriptor backend mismatch.'
Assert-Equal (@($av1NvencPlan.ArgumentList) -join '|') '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|av1_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv' 'AV1/NVENC SDR command topology mismatch.'

$av1NvencHdrPlan = New-PlanFromCase -Overrides @{ VideoCodec = 'av1_nvenc'; IsHDR = $true }
Assert-Equal ([string]$av1NvencHdrPlan.SelectedEncoder) 'av1_nvenc' 'AV1/NVENC HDR plan should expose the descriptor encoder.'
Assert-Equal ([bool]$av1NvencHdrPlan.DescriptorSelection.Active) $true 'AV1/NVENC HDR descriptor selection should be active.'
Assert-Equal (@($av1NvencHdrPlan.ArgumentList) -join '|') '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|av1_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-pix_fmt|p010le|-color_primaries|bt2020|-color_trc|smpte2084|-colorspace|bt2020nc|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv' 'AV1/NVENC HDR command topology mismatch.'

$av1CpuFallbackPlan = New-PlanFromCase -Overrides @{ VideoCodec = 'av1_nvenc'; UseCpuFallback = $true; CpuMaxThreads = 8 }
Assert-Equal ([string]$av1CpuFallbackPlan.SelectedEncoder) 'libaom-av1' 'AV1/NVENC CPU fallback should use the AV1 CPU descriptor encoder.'
Assert-Equal ([string]$av1CpuFallbackPlan.EncoderKind) 'cpu' 'AV1/NVENC CPU fallback should report CPU encoder kind.'
Assert-Equal ([bool]$av1CpuFallbackPlan.DescriptorSelection.Resolved) $true 'AV1/NVENC CPU fallback descriptor selection should resolve.'
Assert-Equal ([bool]$av1CpuFallbackPlan.DescriptorSelection.Active) $true 'AV1/NVENC CPU fallback descriptor selection should be active.'
Assert-Equal ([string]$av1CpuFallbackPlan.DescriptorSelection.Role) 'cpu_fallback' 'AV1/NVENC CPU fallback descriptor role mismatch.'
Assert-Equal ([string]$av1CpuFallbackPlan.DescriptorSelection.DescriptorBackend) 'cpu' 'AV1/NVENC CPU fallback descriptor backend mismatch.'
Assert-Equal (@($av1CpuFallbackPlan.ArgumentList) -join '|') '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libaom-av1|-crf|22|-b:v|0|-cpu-used|1|-threads|8|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv' 'AV1/NVENC CPU fallback command topology mismatch.'

$libaomPrimaryPlan = New-PlanFromCase -Overrides @{ VideoCodec = 'libaom-av1'; CpuMaxThreads = 8 }
Assert-Equal ([string]$libaomPrimaryPlan.SelectedEncoder) 'libaom-av1' 'libaom AV1 primary plan should expose the AV1 CPU descriptor encoder.'
Assert-Equal ([string]$libaomPrimaryPlan.EncoderKind) 'cpu' 'libaom AV1 primary plan should report CPU encoder kind.'
Assert-Equal ([bool]$libaomPrimaryPlan.DescriptorSelection.Resolved) $true 'libaom AV1 primary descriptor selection should resolve.'
Assert-Equal ([bool]$libaomPrimaryPlan.DescriptorSelection.Active) $true 'libaom AV1 primary descriptor selection should be active.'
Assert-Equal ([string]$libaomPrimaryPlan.DescriptorSelection.Role) 'primary' 'libaom AV1 primary descriptor role mismatch.'
Assert-Equal ([string]$libaomPrimaryPlan.DescriptorSelection.DescriptorBackend) 'cpu' 'libaom AV1 primary descriptor backend mismatch.'
Assert-Equal (@($libaomPrimaryPlan.ArgumentList) -join '|') '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libaom-av1|-crf|22|-b:v|0|-cpu-used|1|-threads|8|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv' 'libaom AV1 primary command topology mismatch.'

$h264NvencActivePlan = New-PlanFromCase -Overrides @{ VideoCodec = 'h264_nvenc' }
Assert-Equal ([string]$h264NvencActivePlan.SelectedEncoder) 'h264_nvenc' 'H.264/NVENC active primary plan should expose the descriptor encoder.'
Assert-Equal ([bool]$h264NvencActivePlan.DescriptorSelection.Resolved) $true 'H.264/NVENC descriptor selection should resolve.'
Assert-Equal ([bool]$h264NvencActivePlan.DescriptorSelection.Active) $true 'H.264/NVENC primary descriptor selection should be active.'
Assert-Equal ([string]$h264NvencActivePlan.DescriptorSelection.Family) 'h264' 'H.264/NVENC descriptor family mismatch.'
Assert-Equal ([string]$h264NvencActivePlan.DescriptorSelection.DescriptorBackend) 'nvenc' 'H.264/NVENC descriptor backend mismatch.'
Assert-Equal (@($h264NvencActivePlan.ArgumentList) -join '|') '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|h264_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-profile:v|high|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv' 'H.264/NVENC active primary command topology mismatch.'
Assert-Throws {
    New-PlanFromCase -Overrides @{ VideoCodec = 'h264_nvenc'; IsHDR = $true } | Out-Null
} 'H.264/NVENC active descriptor path must fail closed for HDR sources until HDR preservation is proven.'

$h264CpuFallbackPlan = New-PlanFromCase -Overrides @{ VideoCodec = 'h264_nvenc'; UseCpuFallback = $true; CpuMaxThreads = 8 }
Assert-Equal ([string]$h264CpuFallbackPlan.SelectedEncoder) 'libx264' 'H.264/NVENC CPU fallback should use the H.264 CPU descriptor encoder.'
Assert-Equal ([bool]$h264CpuFallbackPlan.DescriptorSelection.Resolved) $true 'H.264/NVENC CPU fallback descriptor selection should resolve.'
Assert-Equal ([bool]$h264CpuFallbackPlan.DescriptorSelection.Active) $true 'H.264/NVENC CPU fallback descriptor selection should be active.'
Assert-Equal ([string]$h264CpuFallbackPlan.DescriptorSelection.Role) 'cpu_fallback' 'H.264/NVENC CPU fallback descriptor role mismatch.'
Assert-Equal ([string]$h264CpuFallbackPlan.DescriptorSelection.DescriptorBackend) 'cpu' 'H.264/NVENC CPU fallback descriptor backend mismatch.'
Assert-Equal (@($h264CpuFallbackPlan.ArgumentList) -join '|') '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx264|-preset|medium|-crf|20|-threads|8|-profile:v|high|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv' 'H.264/NVENC CPU fallback command topology mismatch.'

$libx264PrimaryPlan = New-PlanFromCase -Overrides @{ VideoCodec = 'libx264'; CpuMaxThreads = 8 }
Assert-Equal ([string]$libx264PrimaryPlan.SelectedEncoder) 'libx264' 'libx264 primary plan should expose the H.264 CPU descriptor encoder.'
Assert-Equal ([bool]$libx264PrimaryPlan.DescriptorSelection.Resolved) $true 'libx264 primary descriptor selection should resolve.'
Assert-Equal ([bool]$libx264PrimaryPlan.DescriptorSelection.Active) $true 'libx264 primary descriptor selection should be active.'
Assert-Equal ([string]$libx264PrimaryPlan.DescriptorSelection.Role) 'primary' 'libx264 primary descriptor role mismatch.'
Assert-Equal ([string]$libx264PrimaryPlan.DescriptorSelection.DescriptorBackend) 'cpu' 'libx264 primary descriptor backend mismatch.'
Assert-Equal (@($libx264PrimaryPlan.ArgumentList) -join '|') '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libx264|-preset|medium|-crf|20|-threads|8|-profile:v|high|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv' 'libx264 primary command topology mismatch.'

$hevcHdrReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'hevc_nvenc' -IsHDR:$true
Assert-Equal ([bool]$hevcHdrReadiness.ok) $true 'HEVC/NVENC HDR should be active for descriptor-owned primary flags.'
Assert-Equal ([string]$hevcHdrReadiness.descriptor_encoder) 'hevc_nvenc' 'HEVC/NVENC readiness descriptor mismatch.'
$h264SdrReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'h264_nvenc'
Assert-Equal ([bool]$h264SdrReadiness.ok) $true 'H.264/NVENC SDR should be active for descriptor-owned primary flags.'
Assert-Equal ([string]$h264SdrReadiness.family) 'h264' 'H.264/NVENC readiness family mismatch.'
$libx264Readiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'libx264'
Assert-Equal ([bool]$libx264Readiness.ok) $true 'libx264 primary should be active for descriptor-owned H.264 CPU flags.'
Assert-Equal ([string]$libx264Readiness.descriptor_encoder) 'libx264' 'libx264 primary readiness descriptor mismatch.'
$h264FallbackReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'h264_nvenc' -UseCpuFallback:$true
Assert-Equal ([bool]$h264FallbackReadiness.ok) $true 'H.264/NVENC CPU fallback should be active for descriptor-owned fallback flags.'
Assert-Equal ([string]$h264FallbackReadiness.descriptor_encoder) 'libx264' 'H.264/NVENC CPU fallback readiness descriptor mismatch.'
$h264HdrReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'h264_nvenc' -IsHDR:$true
Assert-Equal ([bool]$h264HdrReadiness.ok) $false 'H.264/NVENC HDR should fail closed before FFmpeg plan construction.'
Assert-Equal ([string]$h264HdrReadiness.error_code) 'ENCODE_ENCODER_HDR_UNSUPPORTED' 'H.264/NVENC HDR readiness error code mismatch.'
$hevcExplicitNvencReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'hevc_nvenc' -EncoderBackend 'nvenc'
Assert-Equal ([bool]$hevcExplicitNvencReadiness.ok) $true 'Explicit NVENC backend should preserve active HEVC/NVENC literal selection.'
Assert-Equal ([string]$hevcExplicitNvencReadiness.descriptor_encoder) 'hevc_nvenc' 'Explicit HEVC/NVENC readiness descriptor mismatch.'
$libx265ExplicitNvencReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'libx265' -EncoderBackend 'nvenc'
Assert-Equal ([bool]$libx265ExplicitNvencReadiness.ok) $false 'Explicit NVENC backend must not newly activate libx265-to-NVENC override selection.'
Assert-Equal ([string]$libx265ExplicitNvencReadiness.error_code) 'ENCODE_ENCODER_NOT_ACTIVE' 'Explicit libx265-to-NVENC inactive error code mismatch.'
$av1Readiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'av1_nvenc'
Assert-Equal ([bool]$av1Readiness.ok) $true 'AV1/NVENC should be active for literal descriptor-owned selection.'
Assert-Equal ([string]$av1Readiness.descriptor_encoder) 'av1_nvenc' 'AV1/NVENC readiness descriptor mismatch.'
$av1ExplicitNvencReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'av1_nvenc' -EncoderBackend 'nvenc'
Assert-Equal ([bool]$av1ExplicitNvencReadiness.ok) $true 'Explicit NVENC backend should preserve active AV1/NVENC literal selection.'
Assert-Equal ([string]$av1ExplicitNvencReadiness.descriptor_encoder) 'av1_nvenc' 'Explicit AV1/NVENC readiness descriptor mismatch.'
$libaomReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'libaom-av1'
Assert-Equal ([bool]$libaomReadiness.ok) $true 'libaom AV1 primary should be active for descriptor-owned AV1 CPU flags.'
Assert-Equal ([string]$libaomReadiness.descriptor_encoder) 'libaom-av1' 'libaom AV1 primary readiness descriptor mismatch.'
$av1FallbackReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'av1_nvenc' -UseCpuFallback:$true
Assert-Equal ([bool]$av1FallbackReadiness.ok) $true 'AV1/NVENC CPU fallback should be active for descriptor-owned libaom flags.'
Assert-Equal ([string]$av1FallbackReadiness.descriptor_encoder) 'libaom-av1' 'AV1/NVENC CPU fallback readiness descriptor mismatch.'
$av1CpuBackendReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'av1_nvenc' -EncoderBackend 'cpu' -UseCpuFallback:$true
Assert-Equal ([bool]$av1CpuBackendReadiness.ok) $true 'EncoderBackend=cpu should activate the AV1 family CPU descriptor.'
Assert-Equal ([string]$av1CpuBackendReadiness.encoder_backend) 'cpu' 'CPU backend readiness should retain backend evidence.'
Assert-Equal ([string]$av1CpuBackendReadiness.descriptor_encoder) 'libaom-av1' 'CPU backend AV1 readiness descriptor mismatch.'
$av1QsvReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'av1_nvenc' -EncoderBackend 'qsv'
Assert-Equal ([bool]$av1QsvReadiness.ok) $false 'AV1/QSV backend override must stay fail-closed until validation gates are complete.'
Assert-Equal ([string]$av1QsvReadiness.error_code) 'ENCODE_ENCODER_NOT_ACTIVE' 'AV1/QSV inactive readiness error code mismatch.'
$unknownReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec 'vp9_nvenc'
Assert-Equal ([bool]$unknownReadiness.ok) $false 'Unknown encoder readiness must fail closed.'
Assert-Equal ([string]$unknownReadiness.error_code) 'ENCODE_ENCODER_UNSUPPORTED' 'Unknown encoder readiness error code mismatch.'

$encodeImplementationPaths = @(
    (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\encode.ps1')
) + @(Get-ChildItem -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\process') -Filter 'encode_*.ps1' | ForEach-Object { $_.FullName })
$encodeEntryText = ($encodeImplementationPaths | ForEach-Object { Get-Content -LiteralPath $_ -Raw }) -join "`n"
Assert-True ($encodeEntryText -match 'Resolve-MediaEncoderActivationReadiness') 'Do-Encode must check encoder activation before FFmpeg plan construction.'
Assert-True ($encodeEntryText -match '-EncoderBackend \$normalizedEncoderBackend') 'Do-Encode must thread the saved EncoderBackend into activation and attempt planning.'
Assert-True ($encodeEntryText -match 'encoder_backend_cpu_selected') 'Do-Encode must expose EncoderBackend=cpu CPU-only routing evidence.'
Assert-True ($encodeEntryText -match "encoder_activation_policy") 'Do-Encode must emit encoder activation policy evidence.'
Assert-True ($encodeEntryText -match 'Register-SourceFailure[\s\S]+-Stage ''encode-policy''[\s\S]+-ErrorCode \$readinessErrorCode') 'Do-Encode must register inactive encoder selections as encode-policy failures.'

Assert-Throws {
    New-PlanFromCase -Overrides @{ IsHDR = $true; DolbyVisionRpuPath = 'dynamic_hdr\rpu.bin'; DolbyVisionTargetProfile = '8.1' } | Out-Null
} 'Dynamic HDR x265 params must not be accepted by the primary NVENC path.'

Assert-Throws {
    New-PlanFromCase -Overrides @{ VideoCodec = 'av1_nvenc'; IsHDR = $true; Hdr10PlusJsonPath = 'dynamic_hdr\hdr10plus.json' } | Out-Null
} 'Dynamic HDR x265 params must not be accepted by AV1/NVENC primary descriptor paths.'

Assert-Throws {
    New-PlanFromCase -Overrides @{ UseCpuFallback = $true; DolbyVisionRpuPath = 'dynamic_hdr\rpu.bin'; DolbyVisionTargetProfile = '8.1' } | Out-Null
} 'Dynamic HDR x265 params must not be accepted by an SDR CPU plan.'

Assert-Throws {
    New-PlanFromCase -Overrides @{ UseCpuFallback = $true; IsHDR = $true; DolbyVisionRpuPath = 'dynamic_hdr\rpu.bin'; DolbyVisionTargetProfile = '5' } | Out-Null
} 'Dynamic HDR Dolby Vision x265 params must reject unsupported target profiles.'

Assert-Throws {
    New-PlanFromCase -Overrides @{ UseCpuFallback = $true; IsHDR = $true; Hdr10PlusJsonPath = 'C:\scratch\hdr10plus.json' } | Out-Null
} 'Dynamic HDR x265 params must reject colon-bearing Windows paths.'

Assert-Throws {
    New-PlanFromCase -Overrides @{ UseCpuFallback = $true; IsHDR = $true; Hdr10PlusJsonPath = '\\server\scratch\hdr10plus.json' } | Out-Null
} 'Dynamic HDR x265 params must reject rooted artifact paths.'

$metadataAttempts = @($snapshotCases | Select-Object -ExpandProperty Attempt -Unique)
Assert-True ($metadataAttempts -contains 'primary') 'Snapshot set must cover primary attempt metadata.'
Assert-True ($metadataAttempts -contains 'hardware_safe_retry') 'Snapshot set must cover hardware safe-retry attempt metadata.'
Assert-True ($metadataAttempts -contains 'cpu_fallback') 'Snapshot set must cover CPU fallback attempt metadata.'

$fakeNvencEncoderList = @'
 V....D hevc_nvenc           NVIDIA NVENC hevc encoder (codec hevc)
 V....D h264_nvenc           NVIDIA NVENC h264 encoder (codec h264)
'@
Assert-True (Test-NvencEncoderListMatch -EncoderListText $fakeNvencEncoderList -TestEncoder 'hevc_nvenc') 'NVENC startup probe list matching should accept the configured HEVC encoder.'
Assert-True (Test-NvencEncoderListMatch -EncoderListText $fakeNvencEncoderList -TestEncoder ' h264_nvenc ') 'NVENC startup probe list matching should trim and accept the configured H.264 encoder.'
Assert-True (-not (Test-NvencEncoderListMatch -EncoderListText $fakeNvencEncoderList -TestEncoder 'av1_nvenc')) 'NVENC startup probe list matching must not treat HEVC/H.264 NVENC as AV1 NVENC support.'
Assert-True (-not (Test-NvencEncoderListMatch -EncoderListText ' V....D xav1_nvenc' -TestEncoder 'av1_nvenc')) 'NVENC startup probe list matching must not accept suffix-only encoder names.'

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
Assert-Equal (Resolve-MediaEncoderFamilyForCodec -VideoCodec ' hevc_nvenc ') 'hevc' 'Family resolver should trim and map HEVC/NVENC.'
Assert-Equal (Resolve-MediaEncoderFamilyForCodec -VideoCodec 'LIBX265') 'hevc' 'Family resolver should map libx265 case-insensitively.'

$hevcFallbackTarget = Resolve-MediaEncoderCpuFallbackDescriptor -VideoCodec 'hevc_nvenc' -IsHDR:$true
Assert-Equal ([bool]$hevcFallbackTarget.Resolved) $true 'HEVC fallback target should resolve for HDR because libx265 carries HDR10 metadata.'
Assert-Equal ([string]$hevcFallbackTarget.Family) 'hevc' 'HEVC fallback target family mismatch.'
Assert-Equal ([string]$hevcFallbackTarget.EncoderName) 'libx265' 'HEVC fallback target encoder mismatch.'
Assert-Equal ([bool]$hevcFallbackTarget.HdrBlocked) $false 'HEVC fallback target should not be HDR-blocked.'

$hevcAutoSelection = Resolve-MediaEncoderSelection -VideoCodec 'hevc_nvenc'
Assert-Equal ([bool]$hevcAutoSelection.Resolved) $true 'HEVC auto selection should resolve.'
Assert-Equal ([string]$hevcAutoSelection.PrimaryDescriptor.EncoderName) 'hevc_nvenc' 'HEVC auto primary descriptor mismatch.'
Assert-Equal ([string]$hevcAutoSelection.CpuFallbackDescriptor.EncoderName) 'libx265' 'HEVC auto fallback descriptor mismatch.'

$hevcQsvSelection = Resolve-MediaEncoderSelection -VideoCodec 'hevc_nvenc' -EncoderBackend 'qsv'
Assert-Equal ([bool]$hevcQsvSelection.Resolved) $true 'Concrete HEVC/QSV selection should resolve as a scaffold.'
Assert-Equal ([string]$hevcQsvSelection.PrimaryDescriptor.EncoderName) 'hevc_qsv' 'Concrete HEVC/QSV primary descriptor mismatch.'
Assert-Equal ([string]$hevcQsvSelection.CpuFallbackDescriptor.EncoderName) 'libx265' 'Concrete HEVC/QSV fallback descriptor mismatch.'

$hevcQsvUnavailable = Resolve-MediaEncoderSelection -VideoCodec 'hevc_nvenc' -EncoderBackend 'qsv' -CapabilityProbe { param($Descriptor) [pscustomobject]@{ Available = $false; Reason = "probe rejected $($Descriptor.EncoderName)" } }
Assert-Equal ([bool]$hevcQsvUnavailable.Resolved) $true 'Unavailable HEVC/QSV selection should still expose the safe CPU fallback.'
Assert-Equal ($null -eq $hevcQsvUnavailable.PrimaryDescriptor) $true 'Unavailable HEVC/QSV selection must not expose a primary descriptor.'
Assert-Equal ([string]$hevcQsvUnavailable.CpuFallbackDescriptor.EncoderName) 'libx265' 'Unavailable HEVC/QSV fallback descriptor mismatch.'
Assert-True ([string]$hevcQsvUnavailable.Reason -match 'probe rejected hevc_qsv') 'Unavailable HEVC/QSV selection should preserve probe reason.'

$h264NvencDescriptor = Get-MediaEncoderDescriptor -Family 'h264' -Backend 'nvenc'
Assert-True ($null -ne $h264NvencDescriptor) 'Dormant H.264/NVENC descriptor must exist before activation work.'
Assert-Equal ([string]$h264NvencDescriptor.EncoderName) 'h264_nvenc' 'H.264/NVENC descriptor encoder mismatch.'
Assert-Equal ([string]$h264NvencDescriptor.RateControlKind) 'nvenc_cq' 'H.264/NVENC descriptor rate-control mismatch.'
Assert-Equal ([bool]$h264NvencDescriptor.SupportsHdr10Metadata) $false 'H.264/NVENC descriptor must not claim HDR10 metadata support.'
$h264ActiveFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'h264_nvenc' -UseCpuFallback:$false
Assert-True ($null -ne $h264ActiveFlagsDescriptor) 'H.264/NVENC primary flags should now be descriptor-owned.'
Assert-Equal ([string]$h264ActiveFlagsDescriptor.EncoderName) 'h264_nvenc' 'H.264/NVENC active flags descriptor mismatch.'

$h264NvencFlags = @(New-EncoderVideoFlags `
    -Descriptor $h264NvencDescriptor `
    -VideoCodec 'h264_nvenc' `
    -VideoPreset 'p7' `
    -VideoQuality 22)
Assert-Equal (@($h264NvencFlags) -join '|') '-c:v|h264_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-profile:v|high' 'Dormant H.264/NVENC descriptor flags mismatch.'
Assert-Throws { New-EncoderVideoFlags -Descriptor $h264NvencDescriptor -IsHDR:$true -VideoCodec 'h264_nvenc' -VideoPreset 'p7' -VideoQuality 22 | Out-Null } 'H.264/NVENC HDR use must fail closed until HDR preservation is proven.'

$h264CpuDescriptor = Get-MediaEncoderDescriptor -Family 'h264' -Backend 'cpu'
Assert-True ($null -ne $h264CpuDescriptor) 'H.264/CPU descriptor must exist for libx264 activation.'
Assert-Equal ([string]$h264CpuDescriptor.EncoderName) 'libx264' 'H.264/CPU descriptor encoder mismatch.'
Assert-Equal ([string]$h264CpuDescriptor.RateControlKind) 'x264_crf' 'H.264/CPU descriptor rate-control mismatch.'
Assert-Equal ([bool]$h264CpuDescriptor.UsesVbv) $false 'H.264/CPU descriptor must use CRF without VBV.'
$libx264ActiveFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'libx264' -UseCpuFallback:$false
Assert-True ($null -ne $libx264ActiveFlagsDescriptor) 'libx264 primary flags should now be descriptor-owned.'
Assert-Equal ([string]$libx264ActiveFlagsDescriptor.EncoderName) 'libx264' 'libx264 active primary flags descriptor mismatch.'
$h264FallbackFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'h264_nvenc' -UseCpuFallback:$true
Assert-True ($null -ne $h264FallbackFlagsDescriptor) 'H.264/NVENC CPU fallback flags should now be descriptor-owned.'
Assert-Equal ([string]$h264FallbackFlagsDescriptor.EncoderName) 'libx264' 'H.264/NVENC CPU fallback active flags descriptor mismatch.'
$libx264FallbackFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'libx264' -UseCpuFallback:$true
Assert-True ($null -ne $libx264FallbackFlagsDescriptor) 'Literal libx264 CPU fallback flags should be descriptor-owned when called as a fallback.'
Assert-Equal ([string]$libx264FallbackFlagsDescriptor.EncoderName) 'libx264' 'Literal libx264 CPU fallback descriptor mismatch.'
Assert-Equal (Resolve-MediaEncoderFamilyForCodec -VideoCodec 'h264_amf') 'h264' 'Family resolver should map H.264 AMF.'
Assert-Equal (Resolve-MediaEncoderFamilyForCodec -VideoCodec 'libx264') 'h264' 'Family resolver should map libx264.'

$h264FallbackTarget = Resolve-MediaEncoderCpuFallbackDescriptor -VideoCodec 'h264_nvenc'
Assert-Equal ([bool]$h264FallbackTarget.Resolved) $true 'H.264 SDR fallback target should resolve to libx264.'
Assert-Equal ([string]$h264FallbackTarget.EncoderName) 'libx264' 'H.264 fallback target encoder mismatch.'
$h264HdrFallbackTarget = Resolve-MediaEncoderCpuFallbackDescriptor -VideoCodec 'h264_nvenc' -IsHDR:$true
Assert-Equal ([bool]$h264HdrFallbackTarget.Resolved) $false 'H.264 HDR fallback target must stay blocked until HDR preservation is proven.'
Assert-Equal ([bool]$h264HdrFallbackTarget.HdrBlocked) $true 'H.264 HDR fallback target should report HDR blocking.'

$h264HdrSelection = Resolve-MediaEncoderSelection -VideoCodec 'h264_nvenc' -IsHDR:$true
Assert-Equal ([bool]$h264HdrSelection.Resolved) $false 'H.264 HDR selection must fail closed because neither primary nor CPU fallback carries HDR10 metadata.'
Assert-Equal ($null -eq $h264HdrSelection.PrimaryDescriptor) $true 'H.264 HDR selection must not expose a primary descriptor.'
Assert-Equal ($null -eq $h264HdrSelection.CpuFallbackDescriptor) $true 'H.264 HDR selection must not expose an unsafe CPU fallback descriptor.'

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
Assert-True ($null -ne $av1NvencDescriptor) 'AV1/NVENC descriptor must exist for active selection.'
Assert-Equal ([string]$av1NvencDescriptor.EncoderName) 'av1_nvenc' 'AV1/NVENC descriptor encoder mismatch.'
Assert-Equal ([string]$av1NvencDescriptor.RateControlKind) 'nvenc_cq' 'AV1/NVENC descriptor rate-control mismatch.'
Assert-Equal ([bool]$av1NvencDescriptor.SupportsHdr10Metadata) $true 'AV1/NVENC descriptor should be able to carry HDR10 color metadata.'
Assert-Equal ([string](Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'av1_nvenc' -UseCpuFallback:$false).EncoderName) 'av1_nvenc' 'AV1/NVENC primary flags must be descriptor-owned.'
Assert-Equal ([string](Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'av1_nvenc' -EncoderBackend 'nvenc').EncoderName) 'av1_nvenc' 'Explicit AV1/NVENC backend primary flags must be descriptor-owned.'

$av1NvencSdrFlags = @(New-EncoderVideoFlags `
    -Descriptor $av1NvencDescriptor `
    -VideoCodec 'av1_nvenc' `
    -VideoPreset 'p7' `
    -VideoQuality 22)
Assert-Equal (@($av1NvencSdrFlags) -join '|') '-c:v|av1_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M' 'AV1/NVENC SDR descriptor flags mismatch.'
Assert-True (-not (@($av1NvencSdrFlags) -contains '-profile:v')) 'AV1/NVENC must not inherit HEVC profile flags for SDR.'

$av1NvencHdrFlags = @(New-EncoderVideoFlags `
    -Descriptor $av1NvencDescriptor `
    -IsHDR:$true `
    -VideoCodec 'av1_nvenc' `
    -VideoPreset 'p7' `
    -VideoQuality 22)
Assert-Equal (@($av1NvencHdrFlags) -join '|') '-c:v|av1_nvenc|-preset|p7|-cq|22|-maxrate|120M|-bufsize|240M|-pix_fmt|p010le|-color_primaries|bt2020|-color_trc|smpte2084|-colorspace|bt2020nc' 'AV1/NVENC HDR descriptor flags mismatch.'
Assert-True (-not (@($av1NvencHdrFlags) -contains '-profile:v')) 'AV1/NVENC HDR must omit HEVC-style main10 profile flags.'

$av1CpuDescriptor = Get-MediaEncoderDescriptor -Family 'av1' -Backend 'cpu'
Assert-True ($null -ne $av1CpuDescriptor) 'AV1/CPU descriptor must exist for libaom activation.'
Assert-Equal ([string]$av1CpuDescriptor.EncoderName) 'libaom-av1' 'AV1/CPU descriptor encoder mismatch.'
Assert-Equal ([string]$av1CpuDescriptor.RateControlKind) 'aom_crf' 'AV1/CPU descriptor rate-control mismatch.'
Assert-Equal ([bool]$av1CpuDescriptor.SupportsHdr10Metadata) $false 'libaom AV1 descriptor must not claim HDR10 metadata support.'
$libaomActiveFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'libaom-av1' -UseCpuFallback:$false
Assert-True ($null -ne $libaomActiveFlagsDescriptor) 'libaom AV1 primary flags should now be descriptor-owned.'
Assert-Equal ([string]$libaomActiveFlagsDescriptor.EncoderName) 'libaom-av1' 'libaom AV1 active primary flags descriptor mismatch.'
$av1FallbackFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'av1_nvenc' -UseCpuFallback:$true
Assert-True ($null -ne $av1FallbackFlagsDescriptor) 'AV1/NVENC CPU fallback flags should now be descriptor-owned.'
Assert-Equal ([string]$av1FallbackFlagsDescriptor.EncoderName) 'libaom-av1' 'AV1/NVENC CPU fallback active flags descriptor mismatch.'
$libaomFallbackFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec 'libaom-av1' -UseCpuFallback:$true
Assert-True ($null -ne $libaomFallbackFlagsDescriptor) 'Literal libaom AV1 CPU fallback flags should be descriptor-owned when called as a fallback.'
Assert-Equal ([string]$libaomFallbackFlagsDescriptor.EncoderName) 'libaom-av1' 'Literal libaom AV1 CPU fallback descriptor mismatch.'
Assert-Equal (Resolve-MediaEncoderFamilyForCodec -VideoCodec 'av1_qsv') 'av1' 'Family resolver should map AV1 QSV.'
Assert-Equal (Resolve-MediaEncoderFamilyForCodec -VideoCodec 'libaom-av1') 'av1' 'Family resolver should map libaom AV1.'
Assert-Equal (Resolve-MediaEncoderFamilyForCodec -VideoCodec 'libsvtav1') 'av1' 'Family resolver should reserve the future SVT-AV1 family mapping.'

$av1FallbackTarget = Resolve-MediaEncoderCpuFallbackDescriptor -VideoCodec 'av1_nvenc'
Assert-Equal ([bool]$av1FallbackTarget.Resolved) $true 'AV1 SDR fallback target should resolve to libaom-av1.'
Assert-Equal ([string]$av1FallbackTarget.EncoderName) 'libaom-av1' 'AV1 fallback target encoder mismatch.'
$av1HdrFallbackTarget = Resolve-MediaEncoderCpuFallbackDescriptor -VideoCodec 'av1_nvenc' -IsHDR:$true
Assert-Equal ([bool]$av1HdrFallbackTarget.Resolved) $false 'AV1 HDR fallback target must stay blocked until HDR preservation is proven.'
Assert-Equal ([bool]$av1HdrFallbackTarget.HdrBlocked) $true 'AV1 HDR fallback target should report HDR blocking.'

$unknownFallbackTarget = Resolve-MediaEncoderCpuFallbackDescriptor -VideoCodec 'vp9_nvenc'
Assert-Equal ([bool]$unknownFallbackTarget.Resolved) $false 'Unknown fallback target must fail closed.'
Assert-Equal ([string]$unknownFallbackTarget.Family) '' 'Unknown fallback target family should be empty.'

$av1AutoSelection = Resolve-MediaEncoderSelection -VideoCodec 'av1_nvenc'
Assert-Equal ([bool]$av1AutoSelection.Resolved) $true 'AV1 auto selection should resolve as a dormant scaffold.'
Assert-Equal ([string]$av1AutoSelection.PrimaryDescriptor.EncoderName) 'av1_nvenc' 'AV1 auto primary descriptor mismatch.'
Assert-Equal ([string]$av1AutoSelection.CpuFallbackDescriptor.EncoderName) 'libaom-av1' 'AV1 auto fallback descriptor mismatch.'

$av1CpuBackendSelection = Resolve-MediaEncoderSelection -VideoCodec 'av1_nvenc' -EncoderBackend 'cpu'
Assert-Equal ([bool]$av1CpuBackendSelection.Resolved) $true 'AV1 CPU backend selection should resolve.'
Assert-Equal ([string]$av1CpuBackendSelection.PrimaryDescriptor.EncoderName) 'libaom-av1' 'AV1 CPU backend primary descriptor mismatch.'
Assert-Equal ([string]$av1CpuBackendSelection.CpuFallbackDescriptor.EncoderName) 'libaom-av1' 'AV1 CPU backend fallback descriptor mismatch.'

$av1HdrSelection = Resolve-MediaEncoderSelection -VideoCodec 'av1_nvenc' -IsHDR:$true
Assert-Equal ([bool]$av1HdrSelection.Resolved) $true 'AV1/NVENC HDR selection should resolve while CPU fallback stays blocked.'
Assert-Equal ([string]$av1HdrSelection.PrimaryDescriptor.EncoderName) 'av1_nvenc' 'AV1/NVENC HDR primary descriptor mismatch.'
Assert-Equal ($null -eq $av1HdrSelection.CpuFallbackDescriptor) $true 'AV1/NVENC HDR selection must not expose HDR-blocked libaom fallback.'

$libaomHdrSelection = Resolve-MediaEncoderSelection -VideoCodec 'libaom-av1' -IsHDR:$true
Assert-Equal ([bool]$libaomHdrSelection.Resolved) $false 'libaom AV1 HDR selection must fail closed until HDR preservation is proven.'

$svtAv1Selection = Resolve-MediaEncoderSelection -VideoCodec 'libsvtav1'
Assert-Equal ([bool]$svtAv1Selection.Resolved) $false 'SVT-AV1 selection must fail closed until an explicit descriptor exists.'
Assert-True ([string]$svtAv1Selection.Reason -match 'unsupported encoder backend') 'SVT-AV1 selection should explain the missing backend descriptor.'
Assert-Equal ($null -eq $svtAv1Selection.PrimaryDescriptor) $true 'SVT-AV1 selection must not expose a primary descriptor.'
Assert-Equal ($null -eq $svtAv1Selection.CpuFallbackDescriptor) $true 'SVT-AV1 selection must not expose a fallback descriptor without a supported backend.'

$unknownBackendSelection = Resolve-MediaEncoderSelection -VideoCodec 'hevc_nvenc' -EncoderBackend 'bogus'
Assert-Equal ([bool]$unknownBackendSelection.Resolved) $false 'Unknown concrete backend must fail closed.'
Assert-True ([string]$unknownBackendSelection.Reason -match 'unsupported encoder backend') 'Unknown backend selection should explain the invalid backend.'
Assert-Equal ($null -eq $unknownBackendSelection.PrimaryDescriptor) $true 'Unknown backend selection must not expose a primary descriptor.'
Assert-Equal ($null -eq $unknownBackendSelection.CpuFallbackDescriptor) $true 'Unknown backend selection must not expose a fallback descriptor.'

$av1CpuFlags = @(New-EncoderVideoFlags `
    -Descriptor $av1CpuDescriptor `
    -VideoCodec 'libaom-av1' `
    -VideoPreset 'p7' `
    -VideoQuality 22 `
    -FallbackCpuQuality 20 `
    -CpuMaxThreads 8)
Assert-Equal (@($av1CpuFlags) -join '|') '-c:v|libaom-av1|-crf|22|-b:v|0|-cpu-used|1|-threads|8' 'Dormant AV1/CPU descriptor flags mismatch.'
Assert-Throws { New-EncoderVideoFlags -Descriptor $av1CpuDescriptor -IsHDR:$true -VideoCodec 'libaom-av1' -VideoPreset 'p7' -VideoQuality 22 | Out-Null } 'AV1/CPU HDR use must fail closed until HDR preservation is proven.'

$av1CpuBackendPlan = New-PlanFromCase -Overrides @{ VideoCodec = 'av1_nvenc'; EncoderBackend = 'cpu'; CpuMaxThreads = 8 }
Assert-Equal ([string]$av1CpuBackendPlan.Attempt) 'cpu_fallback' 'EncoderBackend=cpu should use the existing CPU fallback attempt shape.'
Assert-Equal ([string]$av1CpuBackendPlan.SelectedEncoder) 'libaom-av1' 'EncoderBackend=cpu should select the AV1 family CPU descriptor.'
Assert-Equal ([bool]$av1CpuBackendPlan.DescriptorSelection.Active) $true 'EncoderBackend=cpu descriptor selection should be active.'
Assert-Equal ([string]$av1CpuBackendPlan.DescriptorSelection.EncoderBackend) 'cpu' 'EncoderBackend=cpu attempt evidence should retain backend evidence.'
Assert-Equal (@($av1CpuBackendPlan.ArgumentList) -join '|') '-i|in.mkv|-map|0:V|-map_chapters|0|-map_metadata|0|-metadata|title=T|-c:v|libaom-av1|-crf|22|-b:v|0|-cpu-used|1|-threads|8|-f|matroska|-max_muxing_queue_size|1024|-y|out.mkv' 'EncoderBackend=cpu AV1 command topology mismatch.'

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

$encodeEntryText = ($encodeImplementationPaths | ForEach-Object { Get-Content -LiteralPath $_ -Raw }) -join "`n"
Assert-True ($encodeEntryText -match '\$cpuMutexWaitSeconds\s*=\s*\[int\]\$script:CpuEncodeMutexWaitSeconds') 'CPU fallback must use the bounded CpuEncodeMutexWaitSeconds setting for mutex waits.'
Assert-True ($encodeEntryText -match 'Acquire-CpuEncodeMutex -TimeoutSeconds \$cpuMutexWaitSeconds') 'CPU fallback must wait for the CPU mutex with the bounded mutex wait after zero-time acquisition fails.'
Assert-True ($encodeEntryText -match 'if \(-not \$cpuMutexLock\.Acquired\)') 'CPU fallback must re-check mutex acquisition after the timed wait.'
Assert-True ($encodeEntryText -match 'ENCODE_CPU_MUTEX_UNAVAILABLE') 'CPU fallback mutex timeout must register a distinct failure code.'
Assert-True ($encodeEntryText -match 'refusing to start overlapping CPU fallback') 'CPU fallback mutex timeout should log a fail-closed operator reason.'

Write-Host "Encode flag policy checks passed. Snapshot count: $(@($snapshotCases).Count)."
