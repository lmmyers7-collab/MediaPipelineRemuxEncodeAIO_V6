# Risk Review

## Executive Risk Posture

The core mutation guards and close-readiness policy are stronger than the command-evidence layer. The review did not find an obvious unconfirmed mutation path or an obvious Tauri close path that silently allows unsafe close during active work. The highest confirmed risk is that backend command exceptions can fail outside the persisted command-result journal, which can make Command History incomplete for failures that matter.

## Command Recording

Strengths:

- Command journal eligibility is schema-gated to `desktop_command_result.v1`.
- Journal entries are bounded and summarized.
- Sensitive terms include network join material such as `join_blob`.
- Validation failures for secret-transfer and unjournaled routes are suppressed.
- UI labels local rows separately from backend journal rows.

Risks:

- Backend route exceptions become generic 500 route-exception payloads and are not command-result schema payloads.
- `_send_json` records only statuses below 400, so backend 500 command failures are omitted from the persisted journal.
- Non-strict journal persistence errors can leave a row visible in memory but not durably written to `RunLogs/local_api_command_history.json`.
- UI merge dedupe uses `command|result|message`, which can collapse repeated identical local failures.

Risk conclusion: command recording is bounded and privacy-aware, but failure evidence is incomplete for backend route exceptions and durability degradation is not visible.

## Bounded History

Strengths:

- Backend journal capacity is enforced on record and output.
- Local UI command history is capped at 20 entries.
- Loaded persisted entries are sanitized before use.

Risks:

- Bounded history necessarily drops older evidence. This is acceptable only if operators understand that Command History is recent evidence, not a complete audit log.
- The SQLite mirror is best-effort and not surfaced as the durable audit source.

Risk conclusion: bounds are correct for UI responsiveness, but they should not be described or treated as a complete audit trail.

## Success And Failure Evidence

Strengths:

- Command result payloads include `ok`, `severity`, message, warnings, errors, log paths, refresh hints, and bounded data.
- Diagnostics formatters attach owner and target actions to command evidence.
- Command History explicitly warns not to infer success from stream visibility.

Risks:

- Backend route exceptions are sent to the caller but not persisted as command failures.
- Local fetch/catch failures are UI-local and disappear across refresh.
- Persistence failures for the backend journal are not included in the command result or `/api/commands` metadata.

Risk conclusion: normal command-result success/failure evidence is good. Exceptional backend failure and journal durability evidence need hardening.

## Confirm Apply And Confirm Save Requirements

Strengths:

- Strict contracts cover rename apply, queue file override series apply, settings save patch, settings wizard save, schedule save, network join/import, and backend shutdown force flags.
- Facades repeat the confirmation checks before mutation.
- Tests reject string booleans for critical confirmation flags.

Risks:

- Strict route mapping must remain synchronized with every future mutation endpoint.
- Base command payloads still allow extra fields for non-strict routes, so the route map is the key boundary.

Risk conclusion: no confirmed strict JSON or missing confirmation defect was found in the reviewed mutation surfaces.

## Shutdown Safety

Strengths:

- Close-readiness aggregates multiple active-work sources.
- Inspection failures mostly fail closed.
- Safe backend shutdown refuses unsafe close.
- Tauri close-readiness errors require confirmation instead of being treated as safe.
- Confirmed force is explicit and sends `force_active_work_shutdown: true`.

Risks:

- Confirmed force intentionally allows termination during active work after user confirmation.
- Live Tauri close during real active encode is not covered by an automated end-to-end test.
- App destroyed/exit events call safe-only shutdown, but process death paths outside normal event handling remain dependent on OS behavior and process-tree cleanup.

Risk conclusion: the implementation is designed to prevent silent unsafe close. The main remaining risk is validation depth for live shell/process behavior.

## Active Encode And Process Detection

Strengths:

- ActiveJobs treats malformed records, missing PIDs, live PIDs, and unverifiable PID identity as blockers.
- Related process scans can block close.
- Fresh pipeline and audit progress can block close.
- Schedule-stop watcher state can block close.

Risks:

- Process identity verification depends on host process inspection behavior.
- Tests use simulated process objects and temp records more than real media subprocesses.

Risk conclusion: active detection is conservative in code, but live validation should be retained as a release gate.

## Diagnostics And Command History Trust

Strengths:

- Diagnostics target opens are allowlisted.
- Command History labels local vs backend journal source.
- Diagnostics copy includes read-first and no-success-inference caveats.

Risks:

- Missing backend journal entries for route exceptions can make the UI look cleaner than the backend actually was.
- Local-only catch rows can be deduped or lost on refresh.
- Command History should remain framed as recent operational evidence, not an audit log.

Risk conclusion: trust language is generally careful, but the backend evidence gap creates a real trust issue.
