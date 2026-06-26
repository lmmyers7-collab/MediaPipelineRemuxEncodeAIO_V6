# Invariants and Boundaries

## Must-Hold Runtime Invariants

1. Subtitle probe uncertainty must block publish.

   Evidence: `Filter-SubtitleStreams` returns `ProbeFailed=$true` on ffprobe failure or invalid JSON, and both encode and remux entrypoints register source failure and return before output work continues.

2. Conversion failures must not produce a trusted output.

   Evidence: `Build-SubtitleArgsForFFmpeg` and `Build-SubtitleTracksForMkvmerge` return `Failures`; `encode.ps1` and `remux.ps1` register subtitle extraction failure and return before publish/final mux proceeds.

3. SRT writes must be atomic and validated.

   Evidence: `Test-SrtFileUsable`, `Complete-AtomicSrtWrite`, and `Copy-SrtAtomic` validate temp/source and final destination.

4. Original subtitles are preserved by default when the output builder/container can carry them.

   Evidence: drop-after-conversion defaults are false; builder decisions preserve original ASS/BDPGS/VobSub/TX3G when compatible and only suppress original preservation when output container/builder cannot carry it or drop flags are explicitly enabled.

5. Image-subtitle OCR must not silently default unknown language to English.

   Evidence: BDPGS and VobSub conversion fail with language-unknown failure codes when language resolves to `und`.

6. OCR tool path failures must route to failure/review, not to publish.

   Evidence: BDPGS and VobSub tool/tessdata/tesseract resolution failures return standard failure records consumed by entrypoint abort logic.

7. Sidecar publish failure must happen before final media reveal and must roll back partial state.

   Evidence: immediate and pending publish paths publish/validate sidecars before final reveal; sidecar failure removes media partials, restores/removes sidecars, records failure state, and returns failure.

8. Review routing must be explicit for unsupported subtitle preservation.

   Evidence: builder decision records mark unsupported BDPGS/TX3G/VobSub/SRT preservation in FFmpeg/MP4 paths with review error codes and failures.

9. Sidecar metadata must carry enough evidence for Completed/QA review.

   Evidence: publish sidecars include `subtitle_decisions`, TX3G SRT tracks/failures, BDPGS/VobSub embedded SRT track arrays, conversion flags, and drop flags.

10. QA surfaces are read-only.

   Evidence: subtitle QA contracts/facade/API assemble existing Queue/Completed evidence only and state mutation guardrails.

## Boundary Decisions

- Backend owns subtitle/media policy. The desktop UI may display policy warnings but must not become the source of truth.
- Media mutation must stay in the PowerShell pipeline and publish transaction modules.
- The Python ASS helper is a conversion helper, not a policy owner.
- Completed QA is a post-run review surface, not a publish safety gate.
- Pending publish state is retryable and must prefer false negatives over trusting incomplete final output.
- External VobSub `.idx`/`.sub` sidecars are discoverable inputs, but they are not copied as original sidecars into final output when conversion is disabled; that condition routes to review.

## High-Risk Boundaries

- FFmpeg MP4 compatibility path, because it cannot embed arbitrary subtitle streams and currently collapses converted SRT candidates to one external sidecar.
- Drop-after-conversion flags, because they intentionally remove original subtitles after generating SRT.
- File override subtitle burn, because it drops selectable subtitle outputs while burning a selected track into video.
- OCR path resolution, because tool/tessdata misses can otherwise become empty or missing text subtitles.
- Pending publish drain, because media output may already exist locally and sidecar failures must not reveal incomplete final state.
