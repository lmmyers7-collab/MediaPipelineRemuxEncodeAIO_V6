# Extracted from ops/pipeline/engine/decide/encoder_descriptors.ps1. Responsibility: encoder descriptors, families, backends, and CPU fallback

function Get-MediaEncoderDescriptor {
    param(
        [Parameter(Mandatory)] [string] $Family,
        [Parameter(Mandatory)] [string] $Backend
    )

    $normalizedFamily = if ($Family) { $Family.Trim().ToLowerInvariant() } else { '' }
    $normalizedBackend = if ($Backend) { $Backend.Trim().ToLowerInvariant() } else { '' }
    $qsvPresetMap = @{
        p1 = 'veryfast'
        p2 = 'faster'
        p3 = 'fast'
        p4 = 'medium'
        p5 = 'slow'
        p6 = 'slower'
        p7 = 'veryslow'
    }
    $amfQualityMap = @{
        p1 = 'speed'
        p2 = 'speed'
        p3 = 'speed'
        p4 = 'balanced'
        p5 = 'balanced'
        p6 = 'quality'
        p7 = 'quality'
    }
    if ($normalizedFamily -eq 'hevc' -and $normalizedBackend -eq 'nvenc') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'hevc_nvenc'
            Family                 = 'hevc'
            Backend                = 'nvenc'
            RateControlKind        = 'nvenc_cq'
            QualityOffset          = 0
            UsesVbv                = $true
            PresetMap              = @{}
            HdrHandlerKind         = 'libav_side_data'
            SupportsHdr10Metadata  = $true
            ProfileArgsSdr         = @('-profile:v', 'main')
            ProfileArgsHdr         = @(
                '-profile:v', 'main10',
                '-pix_fmt', 'p010le',
                '-color_primaries', 'bt2020',
                '-color_trc', 'smpte2084',
                '-colorspace', 'bt2020nc'
            )
            ProbeEncoderName       = 'hevc_nvenc'
            FailurePatternKind     = 'nvenc'
            ContainerNotes         = 'Existing HEVC NVENC behavior; descriptor path must remain argument-identical.'
        }
    }

    if ($normalizedFamily -eq 'hevc' -and $normalizedBackend -eq 'cpu') {
        $encoderName = if (Get-Command -Name Get-MediaVideoCodecLibx265Name -ErrorAction SilentlyContinue) {
            Get-MediaVideoCodecLibx265Name
        } else {
            'libx265'
        }
        return [pscustomobject][ordered]@{
            EncoderName            = $encoderName
            Family                 = 'hevc'
            Backend                = 'cpu'
            RateControlKind        = 'x265_crf'
            QualityOffset          = 0
            UsesVbv                = $false
            PresetMap              = @{}
            HdrHandlerKind         = 'x265_params'
            SupportsHdr10Metadata  = $true
            ProfileArgsSdr         = @('-profile:v', 'main')
            ProfileArgsHdr         = @('-profile:v', 'main10', '-pix_fmt', 'p010le')
            ProbeEncoderName       = 'libx265'
            FailurePatternKind     = 'none'
            ContainerNotes         = 'Existing libx265 CPU fallback behavior; descriptor path must remain argument-identical.'
        }
    }

    if ($normalizedFamily -eq 'hevc' -and $normalizedBackend -eq 'qsv') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'hevc_qsv'
            Family                 = 'hevc'
            Backend                = 'qsv'
            RateControlKind        = 'qsv_global_quality'
            QualityOffset          = 2
            UsesVbv                = $false
            PresetMap              = $qsvPresetMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'hevc_qsv'
            FailurePatternKind     = 'qsv'
            ContainerNotes         = 'Dormant HEVC QSV descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'hevc' -and $normalizedBackend -eq 'amf') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'hevc_amf'
            Family                 = 'hevc'
            Backend                = 'amf'
            RateControlKind        = 'amf_cqp'
            QualityOffset          = 0
            UsesVbv                = $false
            PresetMap              = $amfQualityMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'hevc_amf'
            FailurePatternKind     = 'amf'
            ContainerNotes         = 'Dormant HEVC AMF descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'h264' -and $normalizedBackend -eq 'nvenc') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'h264_nvenc'
            Family                 = 'h264'
            Backend                = 'nvenc'
            RateControlKind        = 'nvenc_cq'
            QualityOffset          = 0
            UsesVbv                = $true
            PresetMap              = @{}
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @('-profile:v', 'high')
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'h264_nvenc'
            FailurePatternKind     = 'nvenc'
            ContainerNotes         = 'Dormant H.264 NVENC descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'h264' -and $normalizedBackend -eq 'cpu') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'libx264'
            Family                 = 'h264'
            Backend                = 'cpu'
            RateControlKind        = 'x264_crf'
            QualityOffset          = 0
            UsesVbv                = $false
            PresetMap              = @{}
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @('-profile:v', 'high')
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'libx264'
            FailurePatternKind     = 'none'
            ContainerNotes         = 'Dormant x264 CPU descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'h264' -and $normalizedBackend -eq 'qsv') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'h264_qsv'
            Family                 = 'h264'
            Backend                = 'qsv'
            RateControlKind        = 'qsv_global_quality'
            QualityOffset          = 2
            UsesVbv                = $false
            PresetMap              = $qsvPresetMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'h264_qsv'
            FailurePatternKind     = 'qsv'
            ContainerNotes         = 'Dormant H.264 QSV descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'h264' -and $normalizedBackend -eq 'amf') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'h264_amf'
            Family                 = 'h264'
            Backend                = 'amf'
            RateControlKind        = 'amf_cqp'
            QualityOffset          = 0
            UsesVbv                = $false
            PresetMap              = $amfQualityMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'h264_amf'
            FailurePatternKind     = 'amf'
            ContainerNotes         = 'Dormant H.264 AMF descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'av1' -and $normalizedBackend -eq 'nvenc') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'av1_nvenc'
            Family                 = 'av1'
            Backend                = 'nvenc'
            RateControlKind        = 'nvenc_cq'
            QualityOffset          = 0
            UsesVbv                = $true
            PresetMap              = @{}
            HdrHandlerKind         = 'libav_side_data'
            SupportsHdr10Metadata  = $true
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @(
                '-pix_fmt', 'p010le',
                '-color_primaries', 'bt2020',
                '-color_trc', 'smpte2084',
                '-colorspace', 'bt2020nc'
            )
            ProbeEncoderName       = 'av1_nvenc'
            FailurePatternKind     = 'nvenc'
            ContainerNotes         = 'Dormant AV1 NVENC descriptor; omits HEVC-style main10 profile flag.'
        }
    }

    if ($normalizedFamily -eq 'av1' -and $normalizedBackend -eq 'qsv') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'av1_qsv'
            Family                 = 'av1'
            Backend                = 'qsv'
            RateControlKind        = 'qsv_global_quality'
            QualityOffset          = 2
            UsesVbv                = $false
            PresetMap              = $qsvPresetMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'av1_qsv'
            FailurePatternKind     = 'qsv'
            ContainerNotes         = 'Dormant AV1 QSV descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'av1' -and $normalizedBackend -eq 'amf') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'av1_amf'
            Family                 = 'av1'
            Backend                = 'amf'
            RateControlKind        = 'amf_cqp'
            QualityOffset          = 0
            UsesVbv                = $false
            PresetMap              = $amfQualityMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'av1_amf'
            FailurePatternKind     = 'amf'
            ContainerNotes         = 'Dormant AV1 AMF descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'av1' -and $normalizedBackend -eq 'cpu') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'libaom-av1'
            Family                 = 'av1'
            Backend                = 'cpu'
            RateControlKind        = 'aom_crf'
            QualityOffset          = 2
            UsesVbv                = $false
            PresetMap              = @{
                p1 = '8'
                p2 = '7'
                p3 = '6'
                p4 = '5'
                p5 = '4'
                p6 = '2'
                p7 = '1'
            }
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'libaom-av1'
            FailurePatternKind     = 'none'
            ContainerNotes         = 'Dormant libaom AV1 descriptor; not selected by the active parity resolver.'
        }
    }

    return $null
}

function Resolve-MediaEncoderDescriptorForFlags {
    param(
        [string] $VideoCodec = '',
        [bool] $UseCpuFallback = $false,
        [string] $EncoderBackend = 'auto'
    )

    $codec = if ($VideoCodec) { $VideoCodec.Trim().ToLowerInvariant() } else { '' }
    $backend = if ($EncoderBackend) { $EncoderBackend.Trim().ToLowerInvariant() } else { 'auto' }
    if ([string]::IsNullOrWhiteSpace($backend)) { $backend = 'auto' }
    $libx265Name = if (Get-Command -Name Get-MediaVideoCodecLibx265Name -ErrorAction SilentlyContinue) {
        (Get-MediaVideoCodecLibx265Name).Trim().ToLowerInvariant()
    } else {
        'libx265'
    }

    if ($UseCpuFallback) {
        if ($codec -in @('hevc_nvenc', $libx265Name)) {
            return Get-MediaEncoderDescriptor -Family 'hevc' -Backend 'cpu'
        }
        if ($codec -in @('h264_nvenc', 'libx264')) {
            return Get-MediaEncoderDescriptor -Family 'h264' -Backend 'cpu'
        }
        if ($codec -in @('av1_nvenc', 'libaom-av1')) {
            return Get-MediaEncoderDescriptor -Family 'av1' -Backend 'cpu'
        }
        return $null
    }

    if ($backend -eq 'cpu') {
        $family = Resolve-MediaEncoderFamilyForCodec -VideoCodec $codec
        if ([string]::IsNullOrWhiteSpace($family)) { return $null }
        return Get-MediaEncoderDescriptor -Family $family -Backend 'cpu'
    }

    if ($backend -eq 'nvenc') {
        if ($codec -eq 'hevc_nvenc') {
            return Get-MediaEncoderDescriptor -Family 'hevc' -Backend 'nvenc'
        }
        if ($codec -eq 'h264_nvenc') {
            return Get-MediaEncoderDescriptor -Family 'h264' -Backend 'nvenc'
        }
        return $null
    }

    if ($backend -ne 'auto') {
        return $null
    }

    if ($codec -eq 'hevc_nvenc') {
        return Get-MediaEncoderDescriptor -Family 'hevc' -Backend 'nvenc'
    }
    if ($codec -eq 'h264_nvenc') {
        return Get-MediaEncoderDescriptor -Family 'h264' -Backend 'nvenc'
    }
    if ($codec -eq 'libx264') {
        return Get-MediaEncoderDescriptor -Family 'h264' -Backend 'cpu'
    }
    if ($codec -eq 'libaom-av1') {
        return Get-MediaEncoderDescriptor -Family 'av1' -Backend 'cpu'
    }
    return $null
}

function Resolve-MediaEncoderFamilyForCodec {
    param(
        [string] $VideoCodec = ''
    )

    $codec = if ($VideoCodec) { $VideoCodec.Trim().ToLowerInvariant() } else { '' }
    $libx265Name = if (Get-Command -Name Get-MediaVideoCodecLibx265Name -ErrorAction SilentlyContinue) {
        (Get-MediaVideoCodecLibx265Name).Trim().ToLowerInvariant()
    } else {
        'libx265'
    }
    if ($codec -eq $libx265Name) { return 'hevc' }
    $familyByCodec = @{
        hevc_nvenc = 'hevc'
        hevc_qsv   = 'hevc'
        hevc_amf   = 'hevc'
        h264_nvenc = 'h264'
        h264_qsv   = 'h264'
        h264_amf   = 'h264'
        libx264    = 'h264'
        av1_nvenc  = 'av1'
        av1_qsv    = 'av1'
        av1_amf    = 'av1'
        'libaom-av1' = 'av1'
        libsvtav1  = 'av1'
    }
    if ($familyByCodec.ContainsKey($codec)) { return [string]$familyByCodec[$codec] }
    return ''
}

function Resolve-MediaEncoderBackendForCodec {
    param(
        [string] $VideoCodec = ''
    )

    $codec = if ($VideoCodec) { $VideoCodec.Trim().ToLowerInvariant() } else { '' }
    $libx265Name = if (Get-Command -Name Get-MediaVideoCodecLibx265Name -ErrorAction SilentlyContinue) {
        (Get-MediaVideoCodecLibx265Name).Trim().ToLowerInvariant()
    } else {
        'libx265'
    }
    if ($codec -eq $libx265Name) { return 'cpu' }
    $backendByCodec = @{
        hevc_nvenc  = 'nvenc'
        hevc_qsv    = 'qsv'
        hevc_amf    = 'amf'
        h264_nvenc  = 'nvenc'
        h264_qsv    = 'qsv'
        h264_amf    = 'amf'
        libx264     = 'cpu'
        av1_nvenc   = 'nvenc'
        av1_qsv     = 'qsv'
        av1_amf     = 'amf'
        'libaom-av1' = 'cpu'
    }
    if ($backendByCodec.ContainsKey($codec)) { return [string]$backendByCodec[$codec] }
    return ''
}

function Resolve-MediaEncoderCpuFallbackDescriptor {
    param(
        [string] $VideoCodec = '',
        [bool] $IsHDR = $false
    )

    $family = Resolve-MediaEncoderFamilyForCodec -VideoCodec $VideoCodec
    $result = [pscustomobject][ordered]@{
        Resolved    = $false
        Reason      = ''
        InputCodec  = [string]$VideoCodec
        Family      = [string]$family
        Backend     = 'cpu'
        EncoderName = ''
        IsHDR       = [bool]$IsHDR
        HdrBlocked  = $false
        Descriptor  = $null
    }

    if ([string]::IsNullOrWhiteSpace($family)) {
        $result.Reason = "unsupported encoder family for codec '$VideoCodec'"
        return $result
    }

    $descriptor = Get-MediaEncoderDescriptor -Family $family -Backend 'cpu'
    if ($null -eq $descriptor) {
        $result.Reason = "missing CPU fallback descriptor for family '$family'"
        return $result
    }

    $result.Descriptor = $descriptor
    $result.EncoderName = [string]$descriptor.EncoderName
    if ($IsHDR -and -not [bool]$descriptor.SupportsHdr10Metadata) {
        $result.HdrBlocked = $true
        $result.Reason = "CPU fallback descriptor '$family/cpu' does not support HDR10 metadata preservation"
        return $result
    }

    $result.Resolved = $true
    $result.Reason = "resolved CPU fallback descriptor '$family/cpu'"
    return $result
}

function New-MediaEncoderSelectionTraceEntry {
    param(
        [Parameter(Mandatory)] [string] $Stage,
        [Parameter(Mandatory)] [string] $Status,
        [Parameter(Mandatory)] [string] $Message,
        $Descriptor = $null,
        [string] $Family = '',
        [string] $Backend = '',
        [string] $EncoderName = ''
    )

    if ($null -ne $Descriptor) {
        if ([string]::IsNullOrWhiteSpace($Family)) { $Family = [string]$Descriptor.Family }
        if ([string]::IsNullOrWhiteSpace($Backend)) { $Backend = [string]$Descriptor.Backend }
        if ([string]::IsNullOrWhiteSpace($EncoderName)) { $EncoderName = [string]$Descriptor.EncoderName }
    }

    return [pscustomobject][ordered]@{
        Stage       = $Stage
        Status      = $Status
        Message     = $Message
        Family      = $Family
        Backend     = $Backend
        EncoderName = $EncoderName
    }
}
