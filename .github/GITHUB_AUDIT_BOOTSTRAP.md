# GitHub Audit Bootstrap

This repository is configured local-first. The files in `.github/` are safe to
commit before a GitHub remote exists. Code Scanning, Dependabot, GitHub labels,
Projects, and repository MCP settings become active after the repository is
pushed to GitHub and the relevant GitHub features are enabled.

## Label Bootstrap

Preview the label commands from the repository root:

```powershell
.\ops\scripts\dev\bootstrap-github-audit-spine.ps1
```

Apply labels after `origin` points at the intended GitHub repository and `gh`
is authenticated:

```powershell
.\ops\scripts\dev\bootstrap-github-audit-spine.ps1 -Apply
```

For a non-`origin` target:

```powershell
.\ops\scripts\dev\bootstrap-github-audit-spine.ps1 -Repository owner/repo -Apply
```

## Project View

Create a GitHub Project manually after labels exist:

- View: `Audit Spine`
- Fields: `Status`, `Risk`, `Area`, `Source`, `Validation`, `Owner`
- Suggested statuses: `Needs triage`, `Needs repro`, `AI ready`,
  `In progress`, `Validation needed`, `Done`
- Saved views:
  - `AI ready`: `label:ai-ready`
  - `High risk`: `label:risk:high,label:risk:critical`
  - `Scanner findings`: `label:source:codeql,label:source:sarif,label:source:dependabot`
  - `Needs validation`: `label:validation-needed`

Keep Code Scanning and Dependabot as the primary alert stores. Convert alerts
to issues only when a finding has been triaged into actionable work.

## GitHub MCP And Copilot

After the repository is hosted on GitHub:

- Enable GitHub Code Scanning and Dependabot in repository security settings
  when the plan/license allows it.
- Use `.github/copilot-instructions.md` as the repository instruction surface
  for Copilot and MCP-backed agents.
- Configure the GitHub MCP server in the IDE, Copilot app, or repository
  settings according to the current GitHub documentation.
- Keep MCP write permissions narrow. Repository, issue, pull request, code
  scanning, and workflow read tools are enough for audit triage; write tools
  should be granted only when an agent is intentionally creating labels,
  comments, branches, issues, or pull requests.
