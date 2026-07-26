# Real-media validation runs

This folder is the operator evidence anchor for representative real-media
validation. Detailed worksheets may contain personal source/output paths, so
release packaging can exclude run-specific files from this folder.

## Historical baseline status

- Status: complete by operator attestation for the 2026-05-28 baseline. This
  does not satisfy the newer recurring rerun gate described below.
- Attested date: 2026-05-28.
- Covered categories: remux, encode/size policy, subtitle conversion, audio
  policy, and pending-publish/final-placement behavior.
- Evidence handling: keep detailed worksheets or local notes outside packaged
  release artifacts when they contain personal paths.

## Post-module-move status

- Status: closed local evidence as of 2026-05-29.
- Full source/dev release self-test passed after the `ops\pipeline\engine\` migration.
- A copied release package with the Tauri executable included launched and
  closed in package mode on this machine.
- Runtime Completed evidence from 2026-05-29 proves real remux/immediate
  publish rows with output/sidecar, audio-copy, subtitle-decision, and
  size-delta fields.
- Scratch-only post-move validation covers forced encode/size policy, subtitle
  conversion, audio evidence, deferred pending publish, drain, and rename-output
  safety without processing the original real source directly.
- The legacy-removal gate is historically closed: `Pipeline\Modules` is no
  longer an active module surface, and active PowerShell implementations live
  under `ops\pipeline\engine\<domain>`. Closure history is indexed from
  `docs/ARCHIVED_MD_INDEX.md`; it is no longer carried as active checklist work.

See `post-module-move-evidence-2026-05-29.md` for the non-sensitive local
evidence summary.

## Tdarr proof-pack media-policy status

- Status: completed local proof-pack rerun for MP-CHANGE-2026-0622-001 on
  2026-06-22.
- Evidence run: `run-20260622-codex-proof-all-final`.
- Covered scope: Tdarr-generated sample matrix remux/encode routing,
  source-video probe behavior, REMUX-AV timestamp synthesis, invalid-container
  failure classification, output probing, and source-hash preservation.
- Result: 92/92 selected cases executed; 76 outputs published and ffprobe
  verified with video streams; 92/92 source hashes unchanged.
- Remaining warnings are fail-closed expected/invalid fixtures: audio-only or
  manifest-mismatched video-missing cases report `SOURCE_MEDIA_VIDEO_MISSING`,
  and the corrupt AVI/rawvideo fixture reports `SOURCE_MEDIA_CONTAINER_INVALID`.
  These warnings are terminal and non-retryable.

## Targeted Dynamic HDR metadata preservation status

- Status: targeted local metadata-preservation proofs complete for the currently
  implemented Dolby Vision P8.1 and HDR10+ encode paths as of 2026-06-22.
- Dolby Vision proof: MP-CHANGE-2026-0622-004, public Dolby Browser Test Kit
  P8.1 SD source, CPU/libx265 encode with FFmpeg native Dolby Vision coding,
  output DOVI verified, source/output RPU frame counts `1721/1721`, source hash
  unchanged.
- HDR10+ proof: MP-CHANGE-2026-0622-007, public FFPictures Lake HDR10+ sample,
  CPU/libx265 encode with relative `dhdr10-info`, output HDR10+ verified,
  source/output extracted HDR10+ JSON hashes matched, source hash unchanged.
- Evidence handling: detailed source/output paths and generated proof artifacts
  remain under gitignored `LocalBase\DynamicHdrValidationRuns\` and
  `LocalBase\DynamicHdrValidationSamples\`.
- Limitation: these are automated metadata-preservation proofs. Playback-device
  Dolby Vision/HDR10+ indicator checks and broader untested profile/source
  combinations remain future real-media validation gates for those cases.

## Revalidation rule

Rerun representative real-media validation whenever FFmpeg command generation,
subtitle conversion/OCR, audio routing, source/scratch/output movement,
pending-publish drain, final publish, or cleanup behavior changes.

## Pending output-verification revalidation

MP-CHANGE-2026-0710-005 adds fail-closed source/output video topology and
resolved audio/subtitle verification before publish, plus Dynamic HDR remux
verification for preservation policies. It is not accepted by this document
until representative encode and remux samples provide source/output ffprobe
JSON, sidecar evidence, Dynamic HDR artifacts where applicable, source hashes,
and playback observations. Dynamic HDR playback-device validation remains a
per-profile gate; no new device compatibility claim is made here.

## 2026-07-11 recurring refresh

- Change packet: `MP-CHANGE-2026-0711-010`.
- Target: branch `refactor/mediapipeline-entrypoint-slice`, clean commit
  `34c194219234fd0a535164038729f110fd7d0f2c` for package evidence.
- Real-media status: blocked before materialization or processing. The strict
  Policy Proof Pack verifier reported that the checked-in catalog still uses
  placeholder SHA-256 values; the configured external fixture root and local
  `policy_proof_sources.json` mapping were also absent. All 15 catalog fixtures
  are therefore unprovisioned. No source media was copied, processed, drained,
  renamed, deleted, or modified, and no current source/output hashes or ffprobe
  evidence were produced.
- Blocked categories: representative remux; encode and size policy; ASS/SSA,
  TX3G, and BDPGS subtitles; multi-language/default audio routing; deferred
  pending publish and backend-owned drain; source-hash preservation; Dynamic
  HDR/profile cases; interruption/rerun resilience; and primary Plex-client
  playback observations.
- Package status: the Tauri release shell built successfully, and clean-HEAD
  portable candidate `MediaPipeline_HEAD_34c1942_Package_20260711` was created
  with 17,302 included files, 5,983 exclusions, no live config, and source
  revision `34c194219234fd0a535164038729f110fd7d0f2c`. Candidate prerequisite
  checks and the copied-package release self-test passed; tool integration and
  end-to-end media were explicitly skipped, and excluded developer-only
  tests/freshness checks remained advisory. ZIP SHA-256 is
  `e74991c0e11f938a0dce3310c1701e16dbbcef1aa160aff044f4bcf872f661e9`;
  packaged shell SHA-256 is
  `c4c1ac275668297f1e9ae7d5ea4083fd12b4aaafe898c17eeb24b8c148d86cdb`.
- Package open/close status: blocked before backend startup because an unrelated
  Tauri development shell already held the per-user single-instance guard.
  The packaged process exited with the expected guard error; API health,
  WebView load, runtime-state externalization, and safe close were not executed
  and are not claimed.

### Final integrated package follow-up

- Change packet: `MP-CHANGE-2026-0711-016`.
- Final validated runtime commit: `52e9be6564aeb13571c0231e2b55ea2903cbc0c0`.
- Deployable package: `MediaPipeline_52e9be65_Deployable_20260711_220735`;
  17,307 files copied, 10,229 excluded, tests and live configuration omitted,
  and `deployable=true` with verification requested in the release manifest.
- Source validation passed with required Python, WebView, PowerShell, tool
  integration, end-to-end, generated-context, environment, and Tauri gates.
- Copied-package and extracted-ZIP acceptance both passed. Each acceptance run
  detected the packaged window and backend, loaded the backend-served WebView,
  externalized runtime state beneath an isolated temporary AppData root, closed
  safely through backend close-readiness, left the install tree immutable, and
  left no Tauri, Local API, PowerShell, or media-tool child process.
- ZIP SHA-256:
  `3a441adfe310fa460fa732b268e3dac8e9c3ba8db0eb1667d48d23f2aebd1a2d`.
  Packaged shell SHA-256:
  `7c1bd389e6f837459691e34510dc436fe51bd5c864eb14bf7700736cc6f10803`.
- A separate launch against the operator's existing per-user runtime state was
  correctly blocked at shutdown by backend close-readiness. That live-state
  safety response was not bypassed and does not invalidate the isolated clean-
  package acceptance above.

Real-media prerequisites and rerun commands:

1. Provision approved owned/sanitized clips for all catalog fixture IDs under
   an external sentinel-controlled PolicyProofPack root.
2. Replace every catalog placeholder with the matching concrete SHA-256 and
   create the external-root-only `policy_proof_sources.json` relative-path
   mapping.
3. Confirm each source matches its required ffprobe topology and that the
   saved policy keeps source deletion/cleanup disabled.
4. Run, substituting the approved external root and a fresh run ID:

   ```powershell
   .\ops\scripts\operator\Invoke-PolicyProofPack.ps1 -Action verify -FixtureRoot '<approved PolicyProofPack root>'
   .\ops\scripts\operator\Invoke-PolicyProofPack.ps1 -Action materialize -RunId 'policy-proof-YYYYMMDD-001' -FixtureRoot '<approved PolicyProofPack root>'
   .\ops\scripts\operator\Invoke-PolicyProofPack.ps1 -Action run -RunId 'policy-proof-YYYYMMDD-001' -FixtureRoot '<approved PolicyProofPack root>'
   ```

5. Complete the worksheet, source before/after hashes, source/output ffprobe
   JSON, manifests/sidecars, pending-publish park/drain proof, and primary
   Plex-client observations required by the active pilot checklist.

Package open/close prerequisite and rerun command: close the existing Tauri
development shell normally, then from the named candidate root run:

```powershell
.\apps\desktop\tauri\Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30
```
