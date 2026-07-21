# Baseline and Provenance Evidence

Capture root: repository root  
Initial capture: `2026-07-19T12:21:05.4735907-04:00` (`2026-07-19T16:21:05.4735907Z`)  
Host: `LAYNE-GAMINGPC`  
OS: Windows `10.0.26200.0`, x64  
Time zone: US Eastern Standard Time, Indiana (East), active offset `-04:00`

## Committed HEAD

- Branch: `codex/ci-browser-shards`.
- Exact HEAD: `a8bf6e1dda9629e6f818ba12f2c8274362923372`.
- Upstream: `origin/codex/ci-browser-shards`.
- Ahead/behind: `0/0` from local refs only; no fetch was performed.
- Remote recorded by Git: `https://github.com/lmmyers7-collab/MediaPipelineRemuxEncodeAIO_V6.git`.
- Latest commit: `fix(queue): harden rerun evidence and freshness`, dated 2026-07-16.
- Recent history was captured with
  `git log -n 15 --date=iso-strict --pretty=format:%H%x09%ad%x09%an%x09%s`.

## Initial Working-Tree Overlay

- 626 unstaged tracked modifications.
- 47 untracked paths.
- 0 staged changes.
- Unstaged diff: 626 files, 20,705 insertions, 5,189 deletions.
- Tracked modification distribution: `docs` 413, `ops` 87, `tests` 47,
  `src` 41, and `apps` 38.
- No submodules.
- Git LFS `3.7.1`; no tracked LFS objects were listed and no LFS objects were
  pending push/commit.

The complete status, tracked name/status list, untracked list, staged status,
diff statistics, upstream relation, remotes, submodule state, and LFS state were
read with the commands listed below. No repository or remote mutation occurred.

## Concurrent Overlay Delta

At `2026-07-19T14:32:50.2157308-04:00`, the shared worktree had changed while
the audit was running:

- 627 tracked modifications.
- 47 untracked paths.
- 0 staged changes.
- 20,716 insertions and 5,190 deletions.
- HEAD was unchanged.
- Post-initial-capture writes were observed on
  `ops/pipeline/engine/naming/movie_cleanup.ps1` and
  `src/mediapipeline/core/rename/movie.py`.

These are recorded as a concurrent user overlay delta. They are not conflated
with the 12:21 baseline and are not audit-owned changes.

Latest snapshot SHA-256 values:

- Full porcelain status: `47196bd51681ecc59b882ae0740e08a966cbbefc7e6d468958592053eade4fc4`.
- Tracked name/status: `87f08270ef23d6d1a453e9350d1c73e07eba4e8dd18be38975cfc3969c255074`.
- Untracked list: `0d328b8c802834f0ff513fc36fe010b0be5bcb1bef9580052e619f60acb8e714`.

## Untracked Inventory at Initial Capture

Top-level counts: `docs` 15, `ops` 12, `.codex-remote-attachments` 9,
`src` 6, `tests` 4, and `apps` 1.

The 47 paths included nine JPG attachments; WebView Run Monitor code; a run
monitor schema and PowerShell state module; three new PowerShell unit checks;
six Python implementation/schema files; four run-monitor contract/service/UI
tests; fifteen generated summaries; and seven unreleased packets:

- `MP-CHANGE-2026-0716-002`.
- `MP-CHANGE-2026-0716-003`.
- `MP-CHANGE-2026-0717-001`.
- `MP-CHANGE-2026-0717-002`.
- `MP-CHANGE-2026-0717-003`.
- `MP-CHANGE-2026-0719-001` (unrelated rename-preview work).
- `MP-CHANGE-2026-0719-002` (this audit campaign).

## Toolchain

| Tool | Version / result |
| --- | --- |
| Bundled Python | 3.11.9 |
| Bundled pip | 24.0 |
| PowerShell Core | 7.6.3 |
| Windows PowerShell | 5.1.26100.8875 |
| Git | 2.54.0.windows.1 |
| Node | 24.15.0 |
| npm | 11.12.1 |
| Cargo | 1.95.0 |
| rustc | 1.95.0 |
| FFmpeg / ffprobe | 8.1 full build (gyan.dev) |
| MKVToolNix | 98.0 |
| .NET | Host present, no SDK; `dotnet --version` exit `-2147450725` |

## Canonical Validation Baseline

Both HEAD and the observed overlay have 48 checked and 5 unchecked checklist
rows. Open items cover encoder breadth/AV1, a separately gated Python
mutation-stage expansion, WebView flat-export cleanup, an upstream-blocked
Linux-only glib/Tauri GTK alert, and the real-media rerun gate.

Recorded—not independently rerun in this capture—evidence includes a 2026-06-22
media-policy run with 92 cases, 76 ffprobe-verified outputs, and 92/92 unchanged
source hashes; targeted multi-video/Dolby Vision/HDR10+ evidence; and an accepted
package/open/close run for integrated runtime commit
`52e9be6564aeb13571c0231e2b55ea2903cbc0c0`. A 2026-07-11 refresh stopped at
strict preflight because 15 catalog hashes were placeholders and required
external fixtures/mapping were absent.

The overlay adds synthetic Run Monitor contract/engine/API/static/browser
coverage claims, while explicitly leaving representative real-media validation
outstanding. Historical attestation and package evidence therefore do not
prove the current 627-file overlay.

## Read-Only Commands

All commands exited 0 except the noted .NET version command:

```text
git branch --show-current
git rev-parse HEAD
git log -n 15 --date=iso-strict --pretty=format:<fields>
git status --branch --untracked-files=all
git status --porcelain=v1 --untracked-files=all
git diff --name-status
git diff --stat
git diff --cached --name-status
git diff --cached --stat
git ls-files --others --exclude-standard
git remote -v
git branch -vv
git rev-parse --abbrev-ref --symbolic-full-name @{upstream}
git rev-list --left-right --count HEAD...@{upstream}
git submodule status --recursive
git lfs version
git lfs status
git lfs ls-files
```

## Limits

- Local upstream comparison was not refreshed from the network.
- Status hashes prove the captured byte sequences but the initial raw sequences
  were not stored in the review pack.
- Concurrent user work means later snapshots must be timestamped and compared,
  not substituted silently for the initial baseline.
- Dirty-state volume does not establish a defect or behavioral delta.

