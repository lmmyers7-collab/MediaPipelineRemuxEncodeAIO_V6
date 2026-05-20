# Logging Convention

> **Status:** Adopt for new code and opportunistic cleanup. Do not mass-rewrite existing log lines.
> **Scope:** PowerShell pipeline logs, Python desktop/backend logs, WebView console usage, and structured state/event artifacts.
> **Companion:** `Docs/DOC_TOUCH_LOG.md` and `Docs/REMEDIATION_CHANGELOG.md` rows for the closed code-management cleanup work.

This project relies on logs as operator evidence. Logs should explain what happened, which subsystem owns the next action, and whether the operator can safely continue. They should not hide backend policy decisions in UI text, and they should not create noise that makes the important evidence hard to find.

---

## Levels

| Level | Use For | Avoid |
|---|---|---|
| `DEBUG` | Developer trace, resolved tool paths, detailed command arguments, bounded diagnostic context. | Operator-facing progress, expected warnings, repeated per-row spam. |
| `INFO` | Normal operator-visible milestones: queue built, scratch copy started, route chosen, output verified, parked for pending publish. | Chatty loops or every tiny helper decision. |
| `WARN` | Recoverable issue where the system chose a safe fallback, skipped risky work, or needs operator attention later. | Expected states that do not need attention. |
| `ERROR` | Failed operation, unsafe precondition, aborted route, failed publish, failed command, or any state that blocks reliable continuation. | Recoverable warnings or validation notes. |

Use the existing `Write-Log "message" "LEVEL"` PowerShell path. `Write-Log` formats lines as:

```text
yyyy-MM-dd HH:mm:ss [LEVEL] message
```

---

## Message Shape

Prefer:

```text
[Module] action/result key=value key=value
```

Examples:

```text
[QueuePlan] built rows=42 excluded=3 strategy=standard
[ScratchCopy] copied source="<leaf>" bytes=123456789
[PendingPublish] parked output; deferred publish pending free-space recovery
```

Rules:

- Use a short module prefix for helper modules: `[QueuePlan]`, `[PendingPublish]`, `[ScratchCopy]`, `[Diagnostics]`.
- Orchestrator-level lines may use the established route prefix: `REMUX:`, `ENCODE:`, `PROCESS:`.
- Include stable identifiers when available: `job_id`, `run_id`, `route`, `source_leaf`, `target`.
- Do not log full source paths at high frequency. Prefer leaf names or backend-allowlisted artifact keys unless the path itself is the evidence.
- Do not log secrets, tokens, SMB credentials, API auth tokens, or full command lines that can contain credentials.
- Do not claim success until the backend has verified the output/state artifact.

---

## Operator Safety Rules

- Source media mutation or deletion must be logged at `WARN` or `ERROR` level unless the explicit destructive toggle is enabled and recorded in the same evidence trail.
- Scratch-copy-first behavior should be visible as `INFO` before media processing starts.
- Route decisions should be logged where the backend decides them, not inferred in frontend copy.
- FFmpeg/mkvmerge wrapper logs should report execution and failure facts, not invent media policy decisions.
- Pending publish parking should distinguish safe parked artifacts from processing failure.
- Recovery instructions should name the backend-owned next action, not ask the operator to edit state files manually.

---

## Structured Artifacts vs Text Logs

Use structured JSON/JSONL state artifacts for machine contracts:

- `pipeline_progress.json`
- `pipeline_events.jsonl`
- command history JSONL
- pending publish manifests
- completed manifests
- failure reports

Use text logs for narrative operator/debug evidence. If the UI or a route needs to make a decision, write/read a structured artifact. Do not parse free-form text logs for backend policy decisions unless the route is explicitly a diagnostics/tail view.

---

## Python Backend Logging

For Python desktop/backend code:

- Prefer existing app/facade logging helpers over `print`.
- Route handlers should return structured error payloads and log enough context to diagnose failed preconditions.
- Do not swallow exceptions silently. If a route returns a safe fallback, the fallback should include operator-visible evidence and the log should include the exception class/message.
- Avoid repeated full-log reads in polling paths; bounded tails and state summaries are preferred.

---

## WebView Console Usage

The WebView should not use console logging as an operator evidence path.

- `console.error` is acceptable for unexpected developer-facing frontend failures that also surface in the UI.
- `console.warn` is acceptable for nonfatal frontend diagnostics during development, but avoid adding permanent warnings for expected empty states.
- `console.log` and `debugger` should not remain in production assets.
- Operator evidence belongs in panels, command result summaries, diagnostics routes, and backend state artifacts.

---

## Cleanup Policy

Adopt this convention when touching an area. Do not mass-edit existing logs just to normalize style.

Safe cleanup examples:

- A chunk that changes pending publish recovery can normalize nearby `[PendingPublish]` log lines.
- A chunk that adjusts route planning can add route decision `INFO` evidence and remove duplicate noisy debug lines.
- A diagnostics route change can replace repeated full-log reads with bounded tail logging.

Unsafe cleanup examples:

- Reformatting every `Write-Log` call in the repo.
- Lowering an `ERROR` to `WARN` to quiet tests without proving recovery is safe.
- Moving a backend route decision into frontend copy because it is easier to display there.
