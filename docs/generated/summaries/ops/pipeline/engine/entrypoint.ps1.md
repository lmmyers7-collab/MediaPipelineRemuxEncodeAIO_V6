---
file: ops/pipeline/engine/entrypoint.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: unknown
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 8b49522fc4597a077cf9073f219055d3a20fbcbf4f32beafebb4e14c787b2586
---
# `ops/pipeline/engine/entrypoint.ps1`

**Purpose:** PowerShell implementation for entrypoint; exposes Assert-AllowedObjectProperties, Assert-StageBooleanField, Assert-StageIntegerField.

**Public symbols:** `Assert-AllowedObjectProperties`, `Assert-StageBooleanField`, `Assert-StageIntegerField`, `Assert-StageNumberField`, `Assert-StageObjectField`, `Assert-StagePayloadContract`, `Assert-StageStringField`, `ConvertTo-DoubleValue`, `ConvertTo-IntValue`, `ConvertTo-JsonText`, `ConvertTo-LongValue`, `ConvertTo-OrderedMap`, `Get-ObjectPropertyNames`, `Get-ObjectValue`, `Get-StagePayload`, `Get-UtcNow`, `New-StageError`, `New-StageErrorFromException`, `Read-PayloadDocument`, `Require-ObjectValue`, `Resolve-StageExecutable`, `Test-JsonBooleanValue`, `Test-JsonIntegerValue`, `Test-JsonNumberValue`, `Test-JsonObjectValue`, `Test-ObjectHasProperty`, `Write-StageResult`
**Invoked stages:** `BooleanField`, `Error`, `ErrorFromException`, `Executable`, `IntegerField`, `Name`, `NumberField`, `ObjectField`, `Payload`, `PayloadContract`, `Result`, `StringField`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/entrypoint.ps1`._
