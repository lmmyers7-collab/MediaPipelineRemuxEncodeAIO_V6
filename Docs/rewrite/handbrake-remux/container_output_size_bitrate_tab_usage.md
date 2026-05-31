# Container, Output Size Check, And Bitrate Gate Tab Usage

Last updated: 2026-05-31

This note explains how a future `Container / Output Size Check` tab should be
used compared with the `Routing` tab, why the concepts should remain separate,
and what benefits and tradeoffs may result. It is documentation only. It does
not change Settings UI behavior, saved config, route decisions, FFmpeg command
generation, publish/drain behavior, or production rollout status.

## Current Position

The current rewrite model separates:

- initial route selection: copy/remux/encode/reject;
- per-stream actions: video, audio, subtitle, and container actions;
- output settings: container, encoder, target mode, bitrate, and quality;
- verification and publish guards: Output Size Check, validation, and
  pending-publish posture.

The UI may place related controls near each other for operator scan speed, but
the underlying decisions should stay separated. `Routing` answers whether the
source can remain copied/remuxed or must encode. `Container / Output Size
Check` should explain output format, bitrate evidence, and post-process trust.

## Tab Responsibilities

| Tab | Primary question | Examples |
| --- | --- | --- |
| `Routing` | Should this source copy/remux, encode, reject, or remain unknown? | Processing Strategy, Route Enforcement Mode, direct-copy bitrate caps, source route-size limits, H.264 compatibility shortcut, direct-copy codec allowlist. |
| `Container / Output Size Check` | If a plan runs, what output container/size/bitrate evidence should the operator trust or review? | MKV/MP4 intent, container compatibility constraints, Output Size Check mode/action, growth tolerances, direct-copy bitrate evidence, encode target/max bitrate evidence, publish blocker posture. |

Routing is decision authority. Container / Output Size Check is consequence and
trust evidence. The second tab can point back to Routing when a value affects
initial route selection, but it should not duplicate route logic.

## How Operators Would Use The Tab

The `Container / Output Size Check` tab should be used after the operator has a
basic route preview or while reviewing a staged settings patch.

Suggested workflow:

1. Start in `Routing` to confirm the Processing Strategy and Route Enforcement
   Mode.
2. Confirm whether source-size and direct-copy bitrate gates are hard route
   triggers or advisory evidence.
3. Move to `Container / Output Size Check` to inspect the proposed output
   container, stream compatibility consequences, bitrate evidence, and
   post-encode Output Size Check posture.
4. If Output Size Check is strict or block-publish, verify whether the outcome
   would fail the job, warn only, or park output through pending publish.
5. Return to `Routing` only when the evidence shows a route decision itself
   should change.

This keeps daily use focused: Routing chooses the processing path; Container /
Output Size Check helps decide whether the resulting output should be trusted,
warned, held, or reviewed.

## What Belongs In Routing

Routing should hold controls and evidence that can change the initial route:

| Concept | Why it belongs in Routing |
| --- | --- |
| `RoutingProfile` / Processing Strategy | It defines the high-level library policy. |
| `RouteThresholdMode` / Route Enforcement Mode | It decides whether size, bitrate, or both are route triggers. |
| `EncodeThresholdGB`, `TVEncodeThresholdGB` | Current behavior uses these as source-size route limits, not output targets. |
| `MovieRouteMaxVideoBitrateMbps`, `TVRouteMaxVideoBitrateMbps` | These are direct-copy source bitrate caps that can force encode. |
| `AllowH264RemuxIfPlexCompatible` | This can keep H.264 sources copied/remuxed when compatible. |
| `H264RemuxMaxBitrateMbps`, `H264RemuxMaxHeight` | These constrain the H.264 direct-copy shortcut. |
| `RemuxSafeVideoCodecs` | Unsafe source codecs should encode or review. |

Routing may display container and size-check summaries, but only as short
evidence. Full explanation belongs in the companion tab.

## What Belongs In Container / Output Size Check

This tab should be used for output consequences and trust checks:

| Concept | Why it belongs here |
| --- | --- |
| `OutputContainer` / container intent | Container choice affects muxing and stream compatibility, but should be explained as output shape. |
| Container action | Shows `keep`, `remux`, or `change` as part of per-stream action evidence. |
| MP4 stream compatibility | MP4 may force audio transcode, subtitle conversion, or subtitle burn-in; this is consequence evidence. |
| Output Size Check action | Shows `disabled`, `warn_only`, `block_publish`, or `fail_job`. |
| Growth tolerance | Explains how much an encoded output may grow before warning, failure, or publish block. |
| Planned target/max bitrate | Explains encode bitrate intent, distinct from source direct-copy caps. |
| Source bitrate evidence | Shows why a source did or did not exceed direct-copy gates, without owning the route decision. |
| Publish blocker summary | Explains whether a size outcome would warn, fail, or park through pending publish. |

The tab should avoid making direct route decisions itself. It should render
backend plan evidence and link to the Routing tab when route-affecting values
need adjustment.

## Why Separate Routing From Container / Output Size Check

The separation prevents three common operator mistakes.

First, it keeps source facts separate from output goals. A source bitrate cap
for direct copy is not the same as an encoded output bitrate target. Putting
both under one undifferentiated "size" panel makes it easy to tune the wrong
knob.

Second, it keeps initial route decisions separate from post-process trust.
`RouteThresholdMode=bitrate` can select encode before any work runs.
`Output Size Check=strict` evaluates an output after encode. Those are different
moments in the pipeline.

Third, it keeps publish safety visible. A bad output-size result should not be
confused with "choose encode." It may warn, fail, or eventually park through
pending publish depending on the policy.

## Bitrate Gate Vocabulary

Use explicit labels because "bitrate" can mean several things.

| Label | Meaning | Route or verification? |
| --- | --- | --- |
| Direct-copy source bitrate cap | Maximum estimated source video bitrate eligible for copy/remux. | Route. |
| H.264 direct-copy max bitrate | H.264 shortcut-specific source bitrate cap. | Route. |
| Encode target bitrate | Desired average bitrate when encoding. | Encode plan. |
| Encode max bitrate | Ceiling for bitrate-constrained encode planning. | Encode plan and verification context. |
| Observed output bitrate | Post-process probe evidence from the produced output. | Verification. |
| Output growth tolerance | Allowed output size growth versus source/expected size. | Verification/publish. |

Direct-copy caps decide whether source video may stay copied. Encode target and
max bitrate describe how encoded output should be created after encode is
already selected. Output growth tolerance decides whether the finished output
is acceptable, advisory, failed, or publish-blocked.

## Benefits

- Reduces confusion between source-size route limits and target output size.
- Makes direct-copy bitrate caps easier to explain without hiding output
  verification.
- Keeps route preview honest: the WebView can show backend route evidence
  without duplicating route logic.
- Helps operators tune container and size trust without accidentally changing
  processing strategy.
- Makes MP4 consequences visible: audio transcode, subtitle conversion, or
  burn-in can be shown as stream-action outcomes.
- Separates pre-run expectations from post-run proof.
- Gives Output Size Check enough room to explain warn-only, fail-job, and
  future block-publish behavior.
- Helps future docs/tests pin whether a changed setting affects route,
  command generation, verification, or publish.

## Costs And Cons

- Some values appear related across two tabs, which can feel like duplication.
- Operators may need cross-links or summary rows to understand why a bitrate
  cap in Routing appears again as evidence in Container / Output Size Check.
- The tab boundary requires disciplined wording. "Size limit" and "bitrate
  limit" are too ambiguous without source/output qualifiers.
- More panels can slow first-time setup if the default view is too dense.
- A split UI can hide cause/effect unless the plan preview clearly says which
  setting changed the route and which setting only changed verification.
- If tests do not pin the boundary, future edits may drift back into duplicate
  frontend routing logic.

## Recommended UI Pattern

Use Routing as the control-heavy tab and Container / Output Size Check as the
evidence-heavy tab.

Routing should show:

- Processing Strategy;
- Route Enforcement Mode;
- movie/TV source route-size limits;
- movie/TV direct-copy bitrate caps;
- H.264 shortcut limits;
- direct-copy video codec allowlist;
- a compact summary of current container and Output Size Check posture.

Container / Output Size Check should show:

- output container selection or summary;
- source container versus planned output container;
- per-stream container consequences;
- direct-copy bitrate evidence copied from backend decision facts;
- encode target/max bitrate evidence from the planned encode output;
- Output Size Check action and tolerance;
- post-process placeholder fields for actual output size/bitrate;
- publish blocker/fail/warn explanation.

When a row is route-authoritative, label it `Routing owns this decision`. When a
row is verification-authoritative, label it `Output Size Check owns this
result`.

## Suggested Preview Rows

| Row | Example status |
| --- | --- |
| Container intent | `MKV output; container action remux; source container MP4.` |
| Stream compatibility | `MP4 target would transcode DTS audio and convert image subtitles.` |
| Direct-copy bitrate gate | `Source estimated 24 Mbps; TV direct-copy cap 18 Mbps; Routing selected ENCODE.` |
| Encode bitrate target | `Target mode average bitrate; target 8 Mbps; max not set.` |
| Output Size Check | `warn_only; 5% quality encode growth tolerance.` |
| Publish posture | `Warnings do not block publish; block-publish is dry-run-only until promoted.` |
| Missing evidence | `Source bitrate missing; Routing treats bitrate cap as advisory/unknown.` |

## Guardrails

- The WebView must not recompute routing from these rows.
- Do not rename legacy keys without a versioned migration phase.
- Do not treat `EncodeThresholdGB` or `TVEncodeThresholdGB` as output size
  targets.
- Do not treat `SizeGuardMode=strict` as pending-publish park behavior in
  current production; current strict behavior is fail-job.
- Keep `block_publish` labelled as dry-run/model-only until a production
  publish/drain implementation is explicitly approved.
- Do not bypass pending publish when final output is unsafe.
- Rerun high-risk validation after any future change to FFmpeg/media policy,
  subtitle/audio behavior, publish/drain behavior, or source/scratch/output
  movement.

## Open Decisions

- Should `Container / Output Size Check` contain editable controls, or should
  it remain mostly evidence with links back to owning tabs?
- Should output bitrate targets live under `Video` only, with this tab showing
  read-only summaries, or should this tab own target/max bitrate controls?
- Should the UI show direct-copy bitrate gates in both tabs, or only summarize
  them in the Container / Output Size Check tab?
- How should future `block_publish` be exposed without implying current
  production support?
- Should MP4 compatibility consequences be shown as a warning, a route reason,
  or a per-stream action table?
- Should output size target fields be added later, separate from current source
  route-size limits?

## Suggested Implementation Path

1. Keep Routing as the route-authoritative tab.
2. Add read-only backend evidence rows to Container / Output Size Check for
   container, bitrate gates, encode target bitrate, Output Size Check action,
   and publish posture.
3. Add tests proving the WebView renders backend evidence without computing
   routing locally.
4. Add copy that always distinguishes source route-size limits from output
   size checks.
5. Only later decide whether any controls should move from Routing or Video
   into this tab.
6. Treat any production change to size/publish behavior as a separate
   high-risk phase with pending-publish and real-media validation.
