# Open Work Checklist

Last audited: 2026-07-20

This file contains only unresolved implementation work and recurring release
gates. Completed work is historical evidence, not backlog. See `CHANGELOG.md`,
`docs/architecture/DECISIONS_AND_HISTORY.md`, `docs/ARCHIVED_MD_INDEX.md`,
the compact `docs/REMEDIATION_CHANGELOG.md` history index, and
`ops/release/changes/` for closed detail.

## Open / Partial Implementation Work

- [ ] **Encoder breadth and AV1** — Descriptor-owned H.264, HEVC, and AV1
  planning/fallback behavior exists. Literal `av1_nvenc` is active for
  `EncoderBackend=auto|nvenc` only after exact encoder-list and runtime probes;
  the current RTX 5080 host passed one-frame and synthetic SDR/HDR10 topology
  checks. Before AV1/NVENC is daily-driver safe, run representative-media
  validation for HDR side data, playback, subtitle/audio/chapter parity,
  quality, and size. QSV and AMF remain fail-closed and require separate
  descriptor, runtime, and real-media activation work. Plan:
  `docs/implementation/encoder-breadth-av1-plan.md`.

- [ ] **Further Python stage mutation expansion (separately gated)** — The
  dispatcher intentionally stops at read-only `probe`/`decide`, guarded
  source-to-scratch `ingest`, scratch-only single-file `rename`, and standalone
  scratch ASS/SSA-to-SRT `subtitle-convert`. PowerShell remains the production
  media engine. `transcode`, `audio-mix`, `publish`, and `drain` stay disabled
  until they reach production-policy, transaction/recovery, journal, trusted
  root, and representative-media parity. Decision: PI-002 in
  `docs/architecture/DECISIONS_AND_HISTORY.md`.

- [ ] **WebView flat-export cleanup** — Namespace-first access is guarded, but
  the authoritative generated inventory still reports 532 flat `window.*`
  assignments across 235 files. Reduce them opportunistically by touched page
  or domain with matching static and browser evidence; do not run an unbounded
  compatibility purge. Inventory:
  `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`.

- [ ] **#15 Linux GTK `glib` Dependabot alert** — Still blocked upstream as of
  2026-07-12. Tauri/Wry currently retains Linux-only GTK 0.18 and `glib` 0.18;
  forcing `glib >= 0.20` is incompatible. This does not affect the Windows
  WebView2 application, but it blocks safe Linux GTK/WebKit packaging. Recheck
  after upstream Tauri/Wry/GTK movement, before adding Linux packaging, or by
  2026-08-07, whichever comes first. Evidence:
  `docs/inventories/RELEASE_DEPENDENCY_REVIEW.md`.

## Recurring Validation Gates

- [ ] **Representative real-media rerun** — Required after Dynamic HDR,
  encoder/media policy, subtitle, audio, publish/drain, source/scratch/output
  movement, cleanup, or other high-risk execution changes. The 2026-07-11
  attempt (MP-CHANGE-2026-0711-010) stopped before materialization because all
  15 checked-in Policy Proof catalog hashes are placeholders, the external
  fixture root is absent, and `policy_proof_sources.json` is not provisioned.
  This gate also carries the newer Run Once monitor's representative
  multi-track/remux/encode/worker/source-unchanged/scratch-copy proof, broader
  Dolby profile and playback-device HDR10+ checks, and relevant Windows/UNC
  filesystem stress when file-handling behavior changes. Prerequisites and
  commands: `docs/RealMediaValidationRuns/README.md`.

  Latest accepted evidence remains reachable there: broad media-policy proof
  MP-CHANGE-2026-0622-001 (92 cases, 76 ffprobe-verified published outputs,
  92/92 source hashes unchanged), multi-video proof MP-CHANGE-2026-0622-003,
  Dolby Vision P8.1 proof MP-CHANGE-2026-0622-004, and HDR10+ metadata proof
  MP-CHANGE-2026-0622-007. Those runs are historical baselines, not proof for
  later high-risk changes.

- [x] **Package/open/close evidence for the current integrated runtime** —
  Satisfied for commit `52e9be6564aeb13571c0231e2b55ea2903cbc0c0` by source
  validation plus isolated copied-folder and extracted-ZIP startup, WebView,
  AppData-state, safe-close, immutable-install-root, and no-leftover-child
  checks. Reopen after launcher, package, Tauri, Local API bootstrap, or release
  layout changes. Evidence: `docs/RealMediaValidationRuns/README.md`.

## Summary Count

| Category | Count |
|---|---:|
| Open implementation or externally blocked items | 4 |
| Currently blocked validation gates | 1 |
| Satisfied recurring gates that reopen on a named trigger | 1 |

<a id="p0--closed-promotion-gates"></a>
<a id="high--closed-local-legacy--packaging-work"></a>
<a id="medium--closed-pre-package--wave-work"></a>
<a id="low--acknowledged-deferred--improvement-backlog"></a>
<a id="2026-06-19-phased-remediation-workstreams"></a>
<a id="completed-elsewhere--no-active-implementation-work"></a>
<a id="deferred--recently-resolved-decisions"></a>

## Historical Evidence

The legacy anchors above preserve practical inbound links from the former
closed-work sections. Their completed detail was removed from this active
checklist and remains reachable through:

- `CHANGELOG.md` for notable project changes and promotion-state updates;
- `docs/REMEDIATION_CHANGELOG.md` for a compact topic/date index into the
  archived 2026-05 remediation entries;
- `docs/architecture/DECISIONS_AND_HISTORY.md` for FR-016, FR-042, dispatcher,
  architecture, and documentation decisions;
- `docs/ARCHIVED_MD_INDEX.md` for completed plan/audit/checklist locations;
- `docs/reviews/*/DISPOSITION_LEDGER.md` for review finding closure; and
- `ops/release/changes/` and `docs/RealMediaValidationRuns/README.md` for
  change-scoped validation evidence.
