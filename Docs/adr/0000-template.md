# NNNN. Short decision title

Status: proposed
Date: YYYY-MM-DD

## Context

Why is this decision being made now? What problem are we solving, what
constraints are forcing the call, and what would happen if we did
nothing? Keep this to the point — a reader new to the project should be
able to understand the situation without opening other files.

Cite the things you read to make the decision (plan sections, prior
ADRs, current-state docs). Do not paste long quotes; link instead.

## Decision

One paragraph stating the decision in plain language, followed by a
short bullet list of the specifics that are now in force. Use the
imperative voice ("Use SQLite as the state store") not the future tense
("We will use…").

If the decision has parts that are explicitly *not* yet decided, list
them in a `## Open questions` section so future ADRs can land them
without ambiguity.

## Consequences

What changes because of this decision? Cover both the things we now do
and the things we now cannot do. Be honest about tradeoffs — a good ADR
names the price, not just the prize.

Typical buckets:

- Code and structure
- Operational surface (logs, state, builds)
- Testing and CI
- Migration cost from the prior state
- Reversibility cost if we change our minds later

## Alternatives considered

For each serious alternative, one paragraph: what it was, why it was
considered, why it was not picked. "We didn't consider any" is rarely
true and almost always wrong to write — if it really was a forced move,
say so and explain why.

## Validation

(Optional but encouraged for runtime-affecting decisions.)

Name the contract test, smoke, or CI check that proves this ADR is in
force in the codebase. Example: `tests/python/contract/test_config_roundtrip.py`
asserts the round-trip property described in `Decision`. If the test
disappears, the ADR is unenforced.

## Supersedes / superseded by

Leave empty until applicable. When superseded, set
`Status: superseded by NNNN` at the top and add a one-line pointer here.
