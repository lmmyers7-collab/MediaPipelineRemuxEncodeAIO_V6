# Change Packet Schema

Change packets are JSON files stored under `changes/unreleased/` or
`changes/released/<version>/`. JSON is used so the tooling has no external YAML
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
- `files_touched`: Files created or modified by the change.
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
  data loss, unsafe cleanup, or broad release/package failure.

## Completion Rule

When `status` is `complete`, the packet must document `summary`, `reason`,
`behavior_before`, `behavior_after`, `files_touched`, `manual_validation`, and
`rollback_plan`. Complete changes without validation and rollback evidence
should fail validation.
