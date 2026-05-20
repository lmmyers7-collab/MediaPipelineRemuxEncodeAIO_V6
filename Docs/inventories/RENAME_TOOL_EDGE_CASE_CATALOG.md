# Rename Tool Edge Case Catalog

Date: 2026-05-14

Documents the expected rename output for Movie and TV rename modes, covering normal cases, edge cases, confidence levels, sidecar behavior, and blocking conditions. Source: `service_rename_movie.py`, `service_rename_tv.py`, `service_rename_planner.py`, `service_rename_preview.py`.

---

## Output Format Patterns

### TV Rename

```
{show_name} - S{season:02d}E{episode:02d}[ - {episode_title}].{ext}
```

Season and episode are zero-padded to 2 digits (e.g., S01E05). Episode title is included only when detected and valid (non-numeric, under 80 characters, not a release tag).

### Movie Rename

```
{Title} ({Year}).{ext}
```

Year is omitted if no year can be extracted from the filename. Title is cleaned of all release/source/audio/service/group tags and title-cased.

---

## TV Rename Examples

### Normal Cases

| Input filename | Auto-detected | Final name | Confidence |
|---|---|---|---|
| `Breaking.Bad.S01E01.1080p.BluRay.mkv` | Show: Breaking Bad, S01E01 | `Breaking Bad - S01E01.mkv` | medium (auto heuristic) |
| `Breaking.Bad.S01E01.Pilot.1080p.BluRay.mkv` | Show: Breaking Bad, S01E01, Title: Pilot | `Breaking Bad - S01E01 - Pilot.mkv` | medium |
| `The.Wire.S03E12.Mission.Accomplished.mkv` | Show: The Wire, S03E12, Title: Mission Accomplished | `The Wire - S03E12 - Mission Accomplished.mkv` | medium |
| `Game.of.Thrones.1x05.mkv` (NxM pattern) | Show: Game of Thrones, S01E05 | `Game of Thrones - S01E05.mkv` | medium |
| S01E01 placed in `Breaking Bad/Season 01/` folder | Show: Breaking Bad (folder), S01E01 | `Breaking Bad - S01E01.mkv` | medium |

### Operator-Supplied Input (High Confidence)

| Operator input | Final name | Confidence |
|---|---|---|
| show_name=`Succession`, season=3, episode=1 | `Succession - S03E01.mkv` | high |
| show_name=`Succession`, season=3, episode=1, no auto-title | `Succession - S03E01.mkv` | high |
| Backend preview returns TV filename | (backend-assigned name, unchanged) | high |

### Episode Title Edge Cases

| Input filename | Title detection | Final name |
|---|---|---|
| `Show.S01E01.1080p.BluRay.mkv` | No title (removed by release tag filter) | `Show - S01E01.mkv` |
| `Show.S01E01.TheTitle.mkv` | Title: TheTitle | `Show - S01E01 - TheTitle.mkv` |
| `Show.S01E01.12345.mkv` | Title rejected (purely numeric) | `Show - S01E01.mkv` |
| `Show.S01E01.A.Very.Long.Episode.Title.That.Exceeds.Eighty.Characters.In.Length.mkv` | Title rejected (>80 chars) | `Show - S01E01.mkv` |
| `Show.S01E01.HEVC.mkv` | Title rejected (looks like a codec tag) | `Show - S01E01.mkv` |

### Season/Episode Detection Priority

| Input signal | Pattern | Priority |
|---|---|---|
| `S01E05` in filename | SxxEyy | Highest (1st) |
| `1x05` in filename | NxM | 2nd |
| `Season 01 Episode 05` in filename | Token pair | 3rd |
| `Season XX` parent folder + filename number | Folder hint | 4th |
| Folder name only | Fallback | Lowest |

---

## Movie Rename Examples

### Normal Cases

| Input filename | Final name | Confidence |
|---|---|---|
| `The.Matrix.1999.1080p.BluRay.HEVC.mkv` | `The Matrix (1999).mkv` | medium |
| `Inception.2010.2160p.UHD.BluRay.TrueHD.Atmos.7.1.mkv` | `Inception (2010).mkv` | medium |
| `Parasite.2019.Korean.BluRay.mkv` | `Parasite (2019).mkv` | medium |
| `The.Dark.Knight.2008.IMAX.mkv` | `The Dark Knight (2008).mkv` | medium (IMAX removed) |
| `Oppenheimer.2023.EXTENDED.mkv` | `Oppenheimer (2023).mkv` | medium (EXTENDED removed) |

### Tags Removed From Movie Filename

| Tag category | Examples removed |
|---|---|
| Video source | `1080p`, `2160p`, `BluRay`, `WEBRip`, `HEVC`, `x264`, `x265`, `av1`, `10bit`, `8bit` |
| Audio | `TrueHD`, `Atmos`, `FLAC`, `Opus`, `EAC3`, `AC3`, `AAC`, `DTS`, `5.1`, `7.1`, `DDPlus` |
| Edition | `EXTENDED`, `REMASTERED`, `PROPER`, `REPACK`, `UNRATED`, `IMAX`, `directors cut` |
| Service/container | `AMZN`, `NF`, `DSNP`, `HMAX`, `Hulu`, `iTunes`, `AppleTV`, `MKV`, `MP4`, `M4V` |
| File size | `1400MB`, `2GB`, `4.7GB` |
| Release group | `RARBG`, `YIFY`, `YTS`, `GalaxyRG`, `BONE`, `PSA`, `Tigole`, `Kris` |
| Parenthetical/bracketed | Any remaining `(...)` or `[...]` content after year extraction |

### Year Detection

| Input pattern | Year extracted |
|---|---|
| `Movie (1999)` | 1999 (parenthetical) |
| `Movie [2010]` | 2010 (bracketed) |
| `Movie 2010 Extra` | 2010 (bare year token) |
| `Movie Without Year` | (none — title only, no year in output) |

### Movie Without Year

```
Input:  SomeOldFilm.BluRay.mkv
Output: Some Old Film.mkv
```

No year parenthetical is added when none can be extracted.

### Operator-Supplied Input (High Confidence)

| Operator input | Final name | Confidence |
|---|---|---|
| movie_title=`The Matrix`, movie_year=1999 | `The Matrix (1999).mkv` | high |
| movie_title=`Alien`, movie_year= (empty) | `Alien.mkv` | high |
| Backend preview returns movie filename | (backend-assigned name, unchanged) | high |

---

## Confidence Levels

| Level | Meaning | When triggered |
|---|---|---|
| `high` | Strong match — backend preview or operator-supplied fields | Backend preview returned a valid TV/Movie filename; operator supplied show+season+episode or title+year |
| `medium` | Auto heuristic — reliable for common patterns | Auto scrub from filename/folder context; no manual input; no backend preview |
| `review` | Warnings present — needs operator inspection before apply | Non-standard extension, path length near 240-char threshold, VLC long-path warning, sidecar issues |
| `blocked` | Cannot apply — errors present | Source file missing, destination conflict, two sources → same destination (duplicate target), invalid extension |

---

## Edge Cases

### Duplicate Target

Two selected sources produce the same destination filename.

```
Source A: Breaking.Bad.S01E01.720p.mkv → Breaking Bad - S01E01.mkv
Source B: Breaking.Bad.S01E01.1080p.mkv → Breaking Bad - S01E01.mkv  ← CONFLICT
```

**Result**: Both rows are `blocked`. The apply button is disabled. The plan must be revised (deselect one or correct inputs) before `rename.apply` can be called.

### Case-Only Change

Source filename differs from destination only in case (e.g., `the wire` → `The Wire`).

```
Source: the.wire.s01e01.mkv
Output: The Wire - S01E01.mkv
```

**Behavior**: Detected as `"case_only"` change kind. Executed via a temp-name swap to avoid case-insensitive filesystem collision on Windows. Safe on NTFS.

### Already-Correct Name

Source filename already matches the destination name.

```
Source: Breaking Bad - S01E01.mkv
Preview output: Breaking Bad - S01E01.mkv
```

**Behavior**: Change kind is `"unchanged"`. Row renders with status `ok` but no filesystem operation is performed when apply is called.

### Missing TV Metadata

No SxxEyy / NxM / episode token found and no operator-supplied fields.

**Behavior**: Row produces a `blocked` result (cannot determine season/episode). Operator must supply `show_name`, `season`, and `start_episode` fields manually.

### Missing Movie Year

No year found in filename and no operator-supplied year.

**Behavior**: Produces `Movie Title.mkv` without a year parenthetical. Confidence is `medium`. Not an error or warning — it is a valid output.

### Non-Standard Extension

Source file has an extension not in `ValidExtensions` (e.g., `.avi`, `.mov`, `.ts` are valid; `.xyz`, `.txt` are not).

**Behavior**: `review` confidence with warning: extension is not in the standard media list. Operator must confirm before apply.

### Path Length Warning

Destination path exceeds 240 characters (VLC_LONG_PATH_THRESHOLD).

**Behavior**: `review` confidence with warning that Windows tools may need long-path support enabled. Apply is not blocked — this is an advisory warning.

### Sidecar Gap (Force Override)

`force_pipeline_name=true` on a row but no existing `.mediapipeline.json` sidecar is found.

**Behavior**: Warning: "no existing sidecar found; force override sidecar will be created." A `.mediapipeline.rename.json` override sidecar will be created on apply.

---

## Sidecar Behavior

When `rename_sidecars=true` (default), the rename service discovers and renames sidecars alongside the media file.

### Sidecar Files Searched and Renamed

| Sidecar pattern | Renamed to |
|---|---|
| `{media_path}.mediapipeline.json` | `{destination}.mediapipeline.json` |
| `{media_path}.pipeline.json` (legacy) | `{destination}.pipeline.json` |
| `{media_path}.mediapipeline.rename.json` | `{destination}.mediapipeline.rename.json` |

### Atomic Rename Behavior

- Media rename and sidecar rename(s) are applied together in a single transaction.
- If any sidecar destination already exists with different content, the operation is blocked.
- If the media rename succeeds but a sidecar rename fails, the service attempts rollback.

### Post-Rename Sidecar Update

After a successful apply, the backend updates the `.mediapipeline.json` sidecar with:

- `output_path` → new destination path
- `output_file` → new filename
- `rename_history` → append entry (most recent 25 entries retained):
  ```json
  {
    "applied_at": "<ISO timestamp>",
    "original_path": "<source>",
    "renamed_path": "<destination>",
    "final_name": "<new filename>",
    "force_pipeline_name": false
  }
  ```

---

## Render Cap Behavior

The Rename table renders up to 250 rows of preview results. If the backend returns more than 250 rows:

- The table shows `250 shown / N checked` disclosure.
- All N rows are included in the backend rename scope — the cap is display-only.
- The apply button covers the full backend-confirmed set, not just the 250 visible rows.

---

## What the Frontend Does Not Control

- Path resolution: the backend resolves absolute paths from its own state, not from frontend-submitted strings.
- Rename execution: `rename.apply` requires `confirm_apply: true`; the backend rebuilds the plan from state independently.
- Sidecar discovery: backend owns the sidecar search; the frontend receives the plan read-only.
- Apply/apply-blocking: the Apply Readiness ledger and duplicate-target guard are enforced at the backend contract layer.

---

## See Also

- Rename command matrix: `Docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- Rename readiness smoke: `Test-WebViewRenameReadinessSmoke.ps1`
- Browser rename smoke: `Test-WebViewBrowserRenameSmoke.ps1`
- Test coverage: `Docs/testing/TEST_COVERAGE_MATRIX.md`
