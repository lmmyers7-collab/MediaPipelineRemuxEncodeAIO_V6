# Change Packet Schema

Change packets are JSON files stored under `ops/release/changes/unreleased/` or
`ops/release/changes/released/<version>/`. JSON is used so the tooling has no external YAML
dependency.

Each packet must use this shape:

```json
{
  "id": "MP-CHANGE-YYYY-MMDD-###",
  "title": "",
  "version_target": "",
  "status": "planned | in_progress | complete",
  "type": "feature | bugfix | behavior_change | refactor | config | schema | docs | test | release | tooling",
  "risk_level": "low | medium | high | critical",
  "date_started": "YYYY-MM-DD",
  "date_completed": null,
  "summary": "",
  "reason": "",
  "affected_areas": [],
  "behavior_before": "",
  "behavior_after": "",
  "files_touched": [],
  "tests_added": [],
  "manual_validation": [],
  "rollback_plan": "",
  "related_changes": [],
  "notes": ""
}
```

## Required Values

- `status`: `planned`, `in_progress`, or `complete`
- `type`: `feature`, `bugfix`, `behavior_change`, `refactor`, `config`,
  `schema`, `docs`, `test`, `release`, or `tooling`
- `risk_level`: `low`, `medium`, `high`, or `critical`

## Field Reference

- `id`: Stable change identifier. It must match the packet filename stem.
- `title`: Short human-readable change title.
- `version_target`: Intended release version or development placeholder.
- `status`: Current packet state.
- `type`: Change category used for changelog and release summaries.
- `risk_level`: Expected risk if this change is shipped.
- `date_started`: Date work began, using `YYYY-MM-DD`.
- `date_completed`: Completion date using `YYYY-MM-DD`, or `null`.
- `summary`: Concise description of what changed.
- `reason`: Why the change exists.
- `affected_areas`: Stable area labels for grouping release impact.
- `behavior_before`: Previous behavior or repository state.
- `behavior_after`: New behavior or repository state.
- `files_touched`: Exact repo-relative forward-slash paths for files created,
  modified, renamed, or deleted by the change. This is the authoritative
  machine-readable coverage field used by strict validation, pre-commit, CI,
  and the Maintenance Change Ledger.
- `tests_added`: Automated tests added by the change, if any.
- `manual_validation`: Manual commands or checks run for the change.
- `rollback_plan`: How to back out the change.
- `related_changes`: Related change IDs.
- `notes`: Additional context, especially for high-risk work.

## Risk Examples

- `low`: Documentation, generated indexes, or isolated tooling with no runtime
  media-processing behavior change.
- `medium`: Local API, validation, or configuration behavior that is covered by
  targeted tests and has limited blast radius.
- `high`: FFmpeg command generation, subtitle/audio policy, publish/drain,
  source/scratch/output movement, queue launch, or settings persistence.
- `critical`: Changes that could cause source mutation, silent bad publish,
  data loss, unsafe cleanup, or broad ops/release/metadata/package failure.

## Completion Rule

When `status` is `complete`, the packet must document `summary`, `reason`,
`behavior_before`, `behavior_after`, `files_touched`, `manual_validation`, and
`rollback_plan`. Complete changes without validation and rollback evidence
should fail validation.

## Coverage Rule

Every meaningful worktree, staged, or branch-diff change must be covered by
`files_touched` in an unreleased packet. Released packets are historical and do
not satisfy current coverage. Generated docs, summaries, tests, scripts, UI
files, config, documentation, and explicit directory subtrees are all coverable
paths; only files Git already ignores are outside coverage.

Use the helper to keep packet fields current without hand-editing JSON:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.record_change_touch MP-CHANGE-YYYY-MMDD-### path/to/file.py
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.record_change_touch MP-CHANGE-YYYY-MMDD-### --from-staged --validation "unit tests - passed"
```
