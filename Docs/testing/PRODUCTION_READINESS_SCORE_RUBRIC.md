# Production readiness score rubric

Use this rubric for production-readiness audits of this repository. It is an
evidence score, not a certification. Score only what the current checkout proves
with local commands, source review, package checks, runtime smoke tests, and
operator-attested validation. Plans, stale evidence, and unrun checks do not
earn points.

## Base score

Start from 0 and add the proven points below. Then apply all hard caps; the
lowest applicable cap wins.

| Area | Points | Evidence required |
| --- | ---: | --- |
| Build, test, and release gates | 20 | Bundled Python tests, PowerShell release/test gates, JS/Tauri checks, dependency checks, and generated-file checks pass or have a documented equivalent. |
| Runtime and data-safety behavior | 20 | Local API or shell starts, health/readiness checks work, source mutation remains forbidden by default, scratch/output cleanup is bounded, close-readiness and duplicate-command guards hold. |
| Security, config, and secrets safety | 15 | Local bind/token/Host/Origin/CORS posture is enforced, strict JSON handling is active, config validation is fail-fast, secrets are not committed or logged, and static files are served safely. |
| Media-policy correctness | 20 | Remux/encode, FFmpeg arguments, audio routing, subtitle conversion/OCR, pending publish/drain, sidecars/manifests, rename, and publish behavior are covered by focused tests and current representative real-media evidence when touched. |
| Operator UX readiness | 10 | Core WebView/Tauri workflows have loading, empty, error, and blocked states; layout is usable at relevant viewport sizes; controls do not bypass backend-owned policy. |
| Observability, rollback, docs, and change control | 15 | Logs/status/command journal expose useful evidence without leaking secrets, rollback paths are documented, release notes or run docs are current, summaries are fresh, and strict change-packet coverage passes. |

## Hard caps

Cap at 69 if any of these are true:

- Sensitive data or mutation routes lack server-side authorization appropriate
  for the configured local/network mode.
- Secrets are exposed in committed files, client bundles, logs, example output,
  or release packages.
- A required migration, backfill, or state repair cannot run safely or lacks a
  rollback/recovery path.
- A high-impact release has no documented rollback path.
- Source media can be deleted or overwritten by default.
- Pending publish or drain can bypass the unsafe-final-root park/drain flow.
- Strict JSON route handling, command journal, duplicate-command guards, or
  backend close-readiness are disabled on mutation-capable paths.

Cap at 84 if any of these are true:

- The relevant CI/local gate set is not green.
- The launch-critical path was not tested end to end by an app-opening smoke or
  documented equivalent.
- This repository has high-risk changes to FFmpeg command generation, subtitle
  conversion/OCR, audio routing, source/scratch/output movement, pending-publish
  drain, final publish, or cleanup behavior and representative real-media
  validation has not been rerun after those changes.

## Real-media evidence rule

Representative real-media validation must cover the categories touched by the
change: remux/direct copy, encode/size policy, preferred-language subtitle
conversion/OCR, audio routing/default language behavior, pending publish/drain,
final placement, sidecars/manifests, and rename/output safety as applicable.

Tiny fixtures, generated smoke files, bundled tool preview files, and ffprobe
JSON fixtures may support unit or smoke coverage, but they do not satisfy the
representative real-media gate. The current evidence anchor is
`Docs/RealMediaValidationRuns/README.md`; its attestation becomes stale for any
later change that touches a listed high-risk media behavior.

## Production target

Score 90 or higher only when:

- no 69 or 84 hard cap applies;
- relevant install/build/lint/test/release gates pass;
- the app or equivalent operator surface starts successfully;
- strict change-control coverage passes; and
- current representative real-media validation exists for every touched
  high-risk media behavior.
