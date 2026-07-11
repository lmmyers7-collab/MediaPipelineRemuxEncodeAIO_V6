# Policy Proof Pack Runbook

Status: active operator validation runbook

## Purpose

The Tdarr Proof Pack is a broad codec/container compatibility suite. The Policy
Proof Pack is its required companion after changes to media routing, subtitles,
audio, Dynamic HDR, encoder selection, scratch/output movement, or pending
publish behavior. It uses owned, sanitized fixtures stored outside Git.

The checked-in catalog at
`tests/fixtures/media_policy/policy_proof_catalog.json` contains logical IDs,
hashes, expected source facts, scenario overlays, and output/publish assertions.
The external fixture root alone contains `policy_proof_sources.json`, which maps
those IDs to fixture-root-relative paths. Do not commit that mapping or media.

## Fixture Provisioning

For every catalog fixture, place an approved sanitized clip under the external
PolicyProofPack root, calculate its SHA-256, record the value in the catalog,
and add its relative path to the local source mapping. A run must fail before
processing when a source is missing, changed, escapes the root, or does not
match its required ffprobe topology.

The catalog covers ASS/SSA, TX3G, BDPGS when configured, multi-language audio,
multi-video/chapters/attachments, timing, SDR 2160p 10-bit, HDR10, HLG, Dolby
Vision P8.1, HDR10+, Dolby Vision P5/P7 remux-or-review, and deferred publish
with sidecars. The interruption fixture must be long enough that its configured
one-second controlled timeout terminates the first worker attempt; the same
isolated source is then rerun and must complete without a source-hash change.

## Commands

Verify sources and topology before processing:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.policy_proof_pack verify
```

The canonical operator wrapper defaults to that non-mutating verification step:

```powershell
.\ops\scripts\operator\Invoke-PolicyProofPack.ps1
```

Materialize an isolated copied run root:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.policy_proof_pack materialize --run-id policy-proof-YYYYMMDD-001
```

Execute one isolated backend-owned worker run per applicable fixture:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.policy_proof_pack run --run-id policy-proof-YYYYMMDD-001
```

`run` writes JSON, Markdown, and CSV reports under the isolated run's
`manifests` directory. Strict mode is the default: every applicable error fails
the command. `--report-only` is for investigation only and is not acceptance
evidence.

## Acceptance

Use the generated report together with the real-media worksheet. On the
operator's primary Plex client, record Direct Play/transcode state, HDR
indicator, subtitle selection/rendering, audio selection, and chapter behavior.
Other devices are optional observations, not substitutes for the primary-client
check.

BDPGS is `not_applicable` only when its conversion path is disabled in the
effective configuration. Dolby Vision P5/P7 must remux or produce explicit
review evidence; only P8.1 has an encode-preservation assertion.

## Safety Boundaries

All writes are under a sentinel-marked PolicyProofPack run child. Sources are
copied before pipeline execution and source hashes are rechecked after it.
The runbook does not authorize changes to FFmpeg arguments, subtitle/audio
policy, or pending-publish behavior. Deferred-publish drain evidence must use
only the isolated test roots and backend-owned drain flow.
