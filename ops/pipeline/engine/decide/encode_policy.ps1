# ==============================================================================
# ops\pipeline\engine\decide\encode_policy.ps1
# ==============================================================================
# Pure encode attempt policy helpers for GPU-first encode and CPU fallback.
#
# These helpers do not read shared state. Callers pass current config values in
# and receive explicit FFmpeg argument lists / attempt metadata back.
# ==============================================================================

$encodePolicyModuleRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $PSCommandPath }
$encoderDescriptorsModule = Join-Path $encodePolicyModuleRoot 'encoder_descriptors.ps1'
if (Test-Path -LiteralPath $encoderDescriptorsModule -PathType Leaf) {
    . $encoderDescriptorsModule
}

. (Join-Path $PSScriptRoot 'encode_policy_arguments.ps1')
. (Join-Path $PSScriptRoot 'encode_policy_planning.ps1')
. (Join-Path $PSScriptRoot 'encode_policy_probe.ps1')
. (Join-Path $PSScriptRoot 'encode_policy_retry.ps1')
