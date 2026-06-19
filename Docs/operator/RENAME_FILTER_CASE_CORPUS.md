# Rename Filter Case Corpus

Use the bad-case corpus when a source folder or file produces a bad rename.
Each captured case becomes a small fixture that can be replayed by tests after
the filter is fixed.

## Add a case

From the repository root:

```powershell
.\ops\scripts\operator\Add-RenameFilterCase.ps1 `
  -SourceFolder "Ascendance of a Bookworm S03+SP 1080p Dual Audio BD Remux FLAC-TTGA" `
  -SourceFile "S03E01-The Beginning of Winter.mkv" `
  -ExpectedName "Ascendance of a Bookworm - S03E01 - The Beginning of Winter.mkv" `
  -ExpectedShow "Ascendance of a Bookworm" `
  -ExpectedSeason 3 `
  -Notes "S03+SP and TTGA leaked into the title."
```

The helper appends to `tests/fixtures/rename/bad_rename_cases.jsonl`.
Store source folder/file names or repo-safe relative paths only; do not store
personal full source roots.

Use `-Status pending` when you want to log a failure before the filter fix is
implemented. Active cases are test gates; pending cases are schema-checked but
not required to pass current rename behavior.

## Validate the corpus

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_rename_bad_case_corpus
```

The active corpus is also safe to include beside focused rename tests after any
rename filter change.
