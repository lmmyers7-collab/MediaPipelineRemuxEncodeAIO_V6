# Final Review Summary

The core subtitle failure gates are strong: subtitle probe failures block encode/remux, conversion/OCR failures for ASS/TX3G/BDPGS/VobSub block encode/remux, unknown bitmap subtitle OCR language fails closed, and sidecar write failures block final media reveal with rollback.

The highest-risk issue is MP4 compatibility behavior. The FFmpeg MP4 path converts eligible subtitle tracks, then selects one converted SRT sidecar candidate and drops the rest from the publish result without durable per-track review/failure evidence. That can produce a successful publish with missing retained subtitles, so it should be treated as high severity.

Other issues are contract and coverage risks:

- Completed-job schema does not enumerate VobSub evidence fields even though runtime sidecars and pending manifests do.
- Blank ASS language is not normalized consistently with TX3G/BDPGS/VobSub and can be dropped under certain overrides.
- Two targeted PowerShell subtitle tests currently fail before assertions due `ops\ops` path resolution.
- Supplemental keyword matching uses wildcard semantics for custom keywords.

Validation performed:

- Subtitle builder decision checks passed.
- OCR promoted path resolution checks passed.
- VobSub subtitle checks passed.
- Sidecar write safety checks passed.
- Pending publish safety checks passed.
- Contract schema checks passed.
- Config key registry checks passed.
- Python subtitle QA tests passed.
- Python config/metadata/web-static/telemetry tests passed with `PYTHONPATH=src`.
- ASS helper pytest tests passed.

Validation not completed:

- `Invoke-SrtValidationChecks.ps1` and `Invoke-FileOverrideSubtitleBurnChecks.ps1` failed before assertions because their repo-root calculations resolved `ops\ops\...`.
- Real-media OCR/playback validation was not run.

Recommended next implementation target:

Fix MP4 compatibility subtitle reduction first by carrying every non-selected converted subtitle candidate into durable sidecar/pending/completed evidence and blocking or routing to review for retained forced/SDH/supplemental losses. Then repair the dead test harnesses and completed-job VobSub schema drift.
