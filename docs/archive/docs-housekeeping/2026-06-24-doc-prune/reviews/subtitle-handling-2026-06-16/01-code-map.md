# Code Map

## Runtime Subtitle Surface

`ops/pipeline/engine/subtitles/subtitles.ps1`

- Public compatibility facade.
- Dot-sources `common.ps1`, `srt.ps1`, `ass.ps1`, `tx3g.ps1`, `bdpgs.ps1`, `vobsub.ps1`, and `builders.ps1`.

`ops/pipeline/engine/subtitles/common.ps1`

- Common timeout, boolean, output-container, configured-path, and progress helpers.
- Dot-sources:
  - `language_policy.ps1`
  - `failure_records.ps1`
  - `routing_decisions.ps1`
  - `filtering.ps1`

`ops/pipeline/engine/subtitles/language_policy.ps1`

- Normalizes blank language to `und`.
- Builds format-specific policy from `Tx3gExtractLanguages`, `BdpgsExtractLanguages`, `VobSubExtractLanguages`, `AssKeepLanguages`, or `SubKeepLanguages`.
- Determines preferred-default and fallback-default language status.

`ops/pipeline/engine/subtitles/routing_decisions.ps1`

- Classifies streams as SRT, ASS, TX3G, BDPGS, VobSub, or unsupported.
- Applies language/title policy, SDH/forced rules, supplemental signs/songs rules, and conversion/keep/drop routing.
- Emits durable subtitle decision records for publish sidecars.

`ops/pipeline/engine/subtitles/filtering.ps1`

- Runs ffprobe subtitle probe.
- Fails closed on probe failure or invalid JSON.
- Applies file override burn/drop/rename policy.
- Scans external VobSub sidecar pairs next to the original source path.
- Produces keep, convert, TX3G convert, BDPGS convert, VobSub convert, burn, drop, and decision arrays.

`ops/pipeline/engine/subtitles/builders/decisions.ps1`

- Plans builder decisions without conversion side effects.
- Determines original preservation vs review routing by builder and output container.
- Marks conversion failures as review routed.
- Forces MP4 compatibility behavior for FFmpeg outputs.

`ops/pipeline/engine/subtitles/builders.ps1`

- Builds mkvmerge subtitle args and FFmpeg subtitle args.
- Runs ASS, TX3G, BDPGS, and VobSub conversions.
- Accumulates failures for entrypoint-level abort.
- In MP4 compatibility mode, suppresses embedded subtitles and exposes one selected converted SRT sidecar candidate.

## Format Modules

`ops/pipeline/engine/subtitles/srt.ps1`

- Validates SRT syntax, non-empty cue text, usable timing, and embedded blank lines.
- Writes SRT atomically with validation before and after destination replacement.
- Copies SRT atomically for sidecar publish.
- Merges adjacent identical cues.

`ops/pipeline/engine/subtitles/ass.ps1`

- Uses the bundled Python helper to convert ASS/SSA streams to SRT.
- Handles karaoke stripping, include/exclude styles, formatting preservation/stripping, timeout/stopped/failed exit codes, SRT validation, and cleanup.

`src/mediapipeline/pipeline/ass_to_srt_cli.py`

- Python CLI for ASS extraction and conversion.
- Guards ffmpeg child lifetime with Windows Job Object/POSIX process groups.
- Performs style filtering, karaoke filtering, overlap splitting/merging, minimum cue gaps, encoding diagnostics, and atomic output writes.

`src/mediapipeline/pipeline/ass_to_srt/`

- Helper modules for ASS events, logging, SRT rendering, style filtering, text cleanup, and timing.

`ops/pipeline/engine/subtitles/tx3g.ps1`

- Detects TX3G/mov_text.
- Converts TX3G to SRT via FFmpeg.
- Generates external SRT sidecar publish plans and records.
- Publishes or exports TX3G SRT sidecars, including existing-output skip handling.

`ops/pipeline/engine/subtitles/bdpgs.ps1`

- Detects BDPGS/PGS.
- Extracts SUP via FFmpeg.
- Resolves PGS OCR tool and optional tessdata path.
- Refuses unknown OCR language instead of defaulting to English.
- OCRs to SRT, repairs common pipe/I glyph errors, validates SRT, and writes atomically.

`ops/pipeline/engine/subtitles/vobsub.ps1`

- Detects embedded VobSub/DVD subtitles.
- Finds external `.idx`/`.sub` pairs.
- Maps embedded ffprobe stream indexes to MKVToolNix track IDs.
- Resolves VobSub OCR tool shape, bundled/system Tesseract, and language data.
- Refuses unknown OCR language and unsupported tool shapes.
- OCRs to SRT, optionally post-processes with `seconv`, validates SRT, and writes atomically.

## Entrypoints and Publish

`ops/pipeline/entrypoints/MediaPipeline/encode.ps1`

- Probes subtitles before encode.
- Aborts on subtitle probe failure.
- Calls FFmpeg subtitle builder.
- Aborts before media encode when subtitle conversion/build failures exist.

`ops/pipeline/entrypoints/MediaPipeline/remux.ps1`

- Probes subtitles before AV remux.
- Aborts on subtitle probe failure.
- Runs expensive subtitle conversion only after AV remux succeeds.
- Aborts before final mkvmerge when subtitle conversion/build failures exist.

`ops/pipeline/entrypoints/MediaPipeline/tx3g_sidecars.ps1`

- Existing-output path for TX3G SRT sidecar export.
- Fails source/review state on subtitle probe or sidecar extraction failure.

`ops/pipeline/engine/publish/publish_completion.ps1`

- Writes immediate publish sidecar evidence before final media reveal.
- Publishes SRT sidecars from plan.
- Rolls back sidecars and parks/removes partial media on sidecar or final reveal failure.

`ops/pipeline/engine/publish/publish_sidecars.ps1`

- Validates sidecar source SRT.
- Backs up existing sidecars.
- Writes SRT sidecars atomically.
- Returns failures and rollback metadata.

`ops/pipeline/engine/publish/pending_park_transaction.ps1`

- Parks local output and pending sidecar files into `PendingServerPush`.
- Stores TX3G, BDPGS, and VobSub conversion evidence arrays in pending manifests.

`ops/pipeline/engine/publish/pending_sidecar_transactions.ps1`

- Validates pending sidecar trust before publish.
- Restores or removes sidecars if pending reveal fails.
- Requires usable pending SRT sidecars before treating an existing server copy as valid.

`ops/pipeline/engine/publish/pending_drain_transaction.ps1`

- Publishes pending media partials and pending SRT sidecars.
- Aborts final reveal and leaves pending retry state on sidecar failure.

## Configuration and UI

`ops/pipeline/engine/config/default_values.ps1`

- Subtitle preservation defaults:
  - `SubKeepLanguages = @('eng','en','und','')`
  - `ConvertTx3gToSrt = $true`
  - `DropTx3gAfterConversion = $false`
  - `ConvertBdpgsToSrt = $false`
  - `DropBdpgsAfterConversion = $false`
  - `ConvertVobSubToSrt = $false`
  - `DropVobSubAfterConversion = $false`
  - `DropAssAfterConversion = $false`

`ops/pipeline/config/MediaPipeline_config_template.psd1`

- Mirrors runtime subtitle defaults in the operator config template.

`src/mediapipeline/contracts/config_validators.py`

- Rejects drop-after-conversion when the matching converter is disabled.
- Requires OCR tool paths when BDPGS or VobSub conversion is enabled.

`apps/desktop/webview/static/assets/settingsView.builders.subtitle.js`

- Provides settings controls and risk warnings for subtitle language filters, conversion switches, drop switches, OCR tools, and OCR conversion readiness.

## QA and Review Routing Surfaces

`src/mediapipeline/contracts/subtitles.py`

- Pydantic contract for subtitle QA result, inventory, and sync review payloads.

`src/mediapipeline/core/subtitles/qa.py`

- Read-only QA builder for Queue and Completed evidence.
- Blocks on explicit subtitle failure evidence.
- Reviews image subtitles without OCR/conversion evidence.
- Does not mutate, probe, OCR, sync, or repair.

`src/mediapipeline/core/subtitles/facade.py`

- Facade mixin that assembles Queue and Completed payloads for QA.

`src/mediapipeline/core/api/commands_subtitle_qa.py`

- Local API command for non-mutating subtitle QA preview.
