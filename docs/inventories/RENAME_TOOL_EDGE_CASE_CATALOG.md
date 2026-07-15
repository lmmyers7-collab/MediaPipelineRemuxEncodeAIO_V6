# Rename Tool Edge Case Catalog

Date: 2026-07-12

Documents the expected rename output for Movie and TV rename modes, covering normal cases, edge cases, confidence levels, sidecar behavior, and blocking conditions. Executable sources are under `src/mediapipeline/core/rename/` (especially `movie.py`, `tv.py`, `tv_folder.py`, `planner.py`, `preview.py`, and `apply.py`) and `ops/pipeline/engine/naming/`.

---

## Output Format Patterns

### TV Rename

```
{show_name} - S{season:02d}E{episode_start:02d}[-E{episode_end:02d}][ - {episode_title}].{ext}
```

Season is zero-padded to two digits. Episodes are zero-padded to at least two digits and may run from E01 through E999. A multi-episode identity uses the canonical `S01E01-E02` form. Episode title is included only when detected and valid: pure numbers, titles longer than 80 characters, and verified release-only tails are omitted, while numeric-leading lexical titles are preserved.

### Movie Rename

```
{Title} ({Year}).{ext}
```

Year is omitted if no year can be extracted from the filename. Title is cleaned of all ops/release/metadata/source/audio/service/group tags and title-cased.

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
| `[SubsPlease] Kanan-sama wa Akumade Choroi - 12v2 (1080p) [80A8418A].mkv` | Show: Kanan-sama wa Akumade Choroi, S01E12, revision: v2 | `Kanan-sama wa Akumade Choroi - S01E12.mkv` | medium |
| `Example Show S01E01_E02v3.mkv` | Show: Example Show, S01E01-E02, revision: v3 | `Example Show - S01E01-E02.mkv` | medium |
| `Example Show 4th Season - 01.mkv` | Show: Example Show, ordinal season 4, E01 | `Example Show - S04E01.mkv` | medium |
| `Example Show OVA - 01.mkv` | Show: Example Show, special season 0, E01 | `Example Show - S00E01.mkv` | medium |

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
| `Show.S01E01.123.Reasons.mkv` | Title retained (numeric-leading lexical text) | `Show - S01E01 - 123 Reasons.mkv` |
| `Show.S01E01.This.Episode.Title.Is.Intentionally.Longer.Than.Eighty.Characters.To.Verify.The.Length.Guard.Rejects.It.mkv` | Title rejected (103 characters after separator normalization) | `Show - S01E01.mkv` |
| `Show.S01E01.HEVC.mkv` | Title rejected (looks like a codec tag) | `Show - S01E01.mkv` |
| `Show.S01E01.A.Proper.Introduction.mkv` | Lexical title retained; `PROPER` is not a verified release-only tail here | `Show - S01E01 - A Proper Introduction.mkv` |

### Season/Episode Detection Priority

| Input signal | Pattern | Priority |
|---|---|---|
| `S01E05`, `S01E05v2`, or canonical range in filename | SxxEyy / revision / SxxEyy-Ezz | Highest; filename supplies season and episode identity |
| `1x05` in filename | NxM | Next episode-token form |
| `Episode 05`, `Ep 05`, or `E05` in filename | Explicit episode token | Next episode-token form; season is resolved separately |
| Delimited anime-style ` - 05` or ` - 05v2` | Bare anime episode | Lowest accepted episode-token form; resolution/year/bit-depth lookalikes are rejected |
| Explicit `Season XX` parent folder + episode-only filename | Folder season | Overrides ordinal/special/default season hints |
| `4th Season`, `Third Season`, or `3rd Cour` in filename | Ordinal season | Used when no stronger filename/folder season exists |
| `OVA`, `OAV`, `ONA`, or `Special` marker/folder | Special season | Maps to S00 unless an explicit filename/folder season is stronger |
| Supplied/default season | Fallback | Used only when no stronger season signal exists |

### Revisions And Multi-Episode Identity

| Input syntax | Interpretation | Canonical result |
|---|---|---|
| `12v2`, `E12v3`, `S01E12v2` | Episode 12 plus uploader revision metadata | `S01E12`; revision is not title text |
| `S01E01E02`, `S01E01-E02`, `S01E01_E02v3` | One file covering episodes 1 through 2 | `S01E01-E02`; revision is discarded from the Plex name |
| `S01E01-E01`, `S01E02-E01`, `S01E01-02`, `Episode 1-2` | Invalid or noncanonical range | Preview is blocked with canonical-format guidance |
| `Show 1-2 S01E03` or title `Part 1-2` | Legitimate numeric title text beside a canonical identity | S01E03 remains authoritative; `1-2` is not reinterpreted as an episode range |

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
| `2001.A.Space.Odyssey.1968.1080p.BluRay.x265.mkv` | `2001 A Space Odyssey (1968).mkv` | medium (rightmost plausible year is the release year) |
| `12.Angry.Men.1957.1080p.BluRay.x264.mkv` | `12 Angry Men (1957).mkv` | medium (numeric title text retained) |
| `A.Proper.Man.2024.mkv` | `A Proper Man (2024).mkv` | medium (metadata-like word retained in lexical title text) |

### Tags Removed From Movie Filename

| Tag category | Examples removed |
|---|---|
| Video source | `1080p`, `2160p`, `BluRay`, `WEBRip`, `HEVC`, `x264`, `x265`, `av1`, `10bit`, `8bit` |
| Audio | `TrueHD`, `Atmos`, `FLAC`, `Opus`, `EAC3`, `AC3`, `AAC`, `DTS`, `5.1`, `7.1`, `DDPlus` |
| Edition/revision metadata tail | `EXTENDED`, `REMASTERED`, `PROPER`, `REPACK`, `RERIP`, `UNRATED`, `IMAX`, `directors cut` when they occur in a verified metadata tail |
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

The rightmost plausible year is used for release names such as `2001.A.Space.Odyssey.1968`; bracketed/parenthesized years take precedence. Plausible numeric title text, years outside the release-year bounds, Roman numerals, and lexical uses of words such as `Proper`, `Web`, `Audio`, `MA`, or `CAM` are preserved unless release-tail evidence or an explicit operator remove term makes them metadata.

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

### Semantic Episode Overlap

Two different target paths still conflict when their parsed TV identities overlap for the same normalized show and season, such as `Show - S01E01-E02.mkv` and `Show - S01E02.mkv`.

**Behavior**: Planning blocks both rows. Apply independently repeats the semantic-overlap check before filesystem mutation.

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
| `{media_stem}.mediapipeline.json` | `{destination_stem}.mediapipeline.json` |
| `{media_stem}.pipeline.json` | `{destination_stem}.pipeline.json` |
| `{media_path}.pipeline.json` (legacy appended form) | `{destination_path}.pipeline.json` |
| `{media_stem}.mediapipeline.rename.json` | `{destination_stem}.mediapipeline.rename.json` |

### Atomic Rename Behavior

- Media rename and sidecar rename(s) are executed as one guarded operation with rollback evidence.
- If any sidecar destination already exists with different content, the operation is blocked.
- If the media rename succeeds but a sidecar rename fails, the service attempts rollback.

### Post-Rename Sidecar Update

After a successful apply, the backend updates existing pipeline metadata sidecars (`.mediapipeline.json`, `.pipeline.json`, and the legacy appended `.pipeline.json` form) with:

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

- Rename command matrix: `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- Rename readiness smoke: `ops/scripts/smoke/Test-WebViewRenameReadinessSmoke.ps1`
- Browser rename smoke: `ops/scripts/smoke/Test-WebViewBrowserRenameSmoke.ps1`
- Test coverage: `docs/testing/TEST_COVERAGE_MATRIX.md`
