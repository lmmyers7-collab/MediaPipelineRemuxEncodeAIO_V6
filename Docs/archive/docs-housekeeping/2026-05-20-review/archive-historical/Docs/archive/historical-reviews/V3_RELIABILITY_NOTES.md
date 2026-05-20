# V5 Reliability Baseline Inherited From V4 Hardening

Historical filename retained for compatibility with older notes. The content below describes the reliability posture V5 inherited from the V4 cleanup and hardening baseline.

This fork applies the reliability fixes from the adversarial Python audit and the later V4 cleanup/hardening passes.

Implemented changes:

- Atomic writes for:
  - desktop app state
  - saved config documents
  - subtitle helper summary JSON
  - subtitle helper SRT output
  - tx3g and BDPGS generated SRT files
  - pending-push manifests
- Non-modal polling errors in the desktop app
  - refresh failures now log and update status instead of blocking the UI with repeated dialogs
- Background telemetry worker
  - CPU and NVENC sampling no longer block the main UI refresh path
- Incremental log tail reads
  - the app now reads only the tail of `pipeline_debug.log` instead of re-reading the full file on every poll
- Safer extra-argument parsing
  - quoted values are preserved instead of being split on raw spaces
- Queue refresh improvements
  - removed duplicate sorts
  - removed repeated `stat()` calls from the queue sort key
  - cached mtimes during queue construction
- Cross-platform process handling improvements
  - non-Windows child processes are launched in their own session and killed as a group
- Subtitle helper hardening
  - temp ASS file is created inside the guarded cleanup scope
  - fallback subtitle encodings are attempted after UTF-8
  - output directories are created before writing
  - summary write failures no longer hide the original error
  - Windows Job Object initialization closes handles on setup failure
- Subtitle pipeline hardening
  - tx3g/mov_text tracks are detected from `codec_name`, `codec_tag_string`, and MP4 Timed Text long names
  - tx3g conversion and tx3g preservation are separate decisions
  - ASS conversion failures produce structured failure records instead of silent subtitle loss
  - BDPGS OCR writes to temp SRT files and validates before publishing/muxing
  - BDPGS tessdata paths are resolved relative to the portable `Pipeline\` folder
  - deferred publish manifests carry generated SRT sidecars with the media file
  - missing pending sidecars are classified into the failure workspace
- Audio hardening
  - audio passthrough/transcode behavior is controlled by named profiles plus codec/bitrate/downmix/max-channel settings
  - PCM audio codecs are forced through the configured normalization path
  - audio language/default/forced disposition metadata is preserved where possible during normalization
- Routing hardening
  - Plex Direct/Stream is the default profile, with stricter Direct Play and archive/manual profiles available
  - H.264 can remux/copy when source profile, bitrate, and resolution are already policy-compatible
  - encode growth can be advisory, strict, or disabled
  - route reason, decision trace, source media profile, and encode attempts are persisted into sidecars and pending-push manifests
- Rename hardening
  - standalone Rename tab is separate from the queue
  - TV renaming follows explicit selected row order
  - movie prediction uses pipeline naming rules by default and selectable built-in scrub filters when the operator customizes categories
  - already-correct filenames are shown as `match` rather than warning rows
- Maintainability hardening
  - audit progress, probe cache, issue policy, report writing, and scanner loops are split into focused PowerShell modules
  - desktop service behavior is split into focused `service_*.py` mixins with `services.py` retained as the stable facade
  - desktop blocking refresh/load work is routed through a UI-safe background worker queue
  - migration-only module-extraction scaffolding was removed from the main pipeline script; retained compatibility facades are documented as supported entrypoints
- Control-surface hardening
  - process launches write active job records and expose stdout/stderr run logs
  - Kill + Quit verifies related process-tree termination and clears known runtime control/progress artifacts
  - Clear Failure Errors is constrained to failure-state roots and writes a clear manifest
  - config save/profile load paths validate PSD1 syntax and managed config values before replacement
- Deployability hardening
  - live operator config remains local to the working folder
  - new-user release builds strip personal config and generated clutter by default
  - `MediaPipeline_config_template.psd1` is the non-personal starter config

Remaining constraints:

- Queue refresh still walks the source trees through the pipeline dry-run path. It is authoritative and safer than local UI planning, but it is not yet a persistent source index.
- The desktop app still assumes Windows-first behavior for the deployment environment, even though several service helpers now degrade more cleanly on non-Windows systems.
- BDPGS OCR quality depends on source image quality and installed Tesseract language data.
