# Claude Code repository instructions

`AGENTS.md` is the authoritative operating contract. Do not duplicate or
override its safety, placement, change-control, validation, or media-boundary
rules here.

For non-trivial repository work:

1. Read `AGENTS.md`.
2. Use the local `mediapipeline-code` MCP server exactly as its AI Navigation
   Workflow describes: `repo_context`, then focused lookup/search and bounded
   reads.
3. If MCP is unavailable, use the documented `context_slice` CLI fallback.
4. Open status, backlog, architecture, boundary, summary, source, and test files
   only when the task capsule or `AGENTS.md` makes them relevant.

Never load `PROJECT_INDEX.md`, `PROJECT_INDEX.jsonl`, the whole summary tree,
or all orientation documents as routine startup context. Preserve unrelated
dirty worktree changes, use bundled project runtimes, create or update the
required change packet, and do not commit or push unless the operator asks.

For high-risk media, publish/drain, queue, settings, lifecycle, rename, or
source/output movement work, follow the validation rung and no-touch boundary
from `AGENTS.md`; token reduction never removes those safety requirements.
