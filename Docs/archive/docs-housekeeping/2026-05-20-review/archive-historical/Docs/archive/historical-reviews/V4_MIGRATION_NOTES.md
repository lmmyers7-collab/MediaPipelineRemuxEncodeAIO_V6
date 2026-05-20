# MediaPipelineRemuxEncodeAIO V4 Migration Notes

This folder was created as a curated V4 export from `MediaPipelineRemuxEncodeAIO_V3`.

Included in the active V4 working folder:
- runtime/source files required for the portable Windows app
- `DesktopApp`
- `Pipeline`
- bundled PowerShell, Python runtime, FFmpeg, MKVToolNix, and related tools
- current config, docs, launchers, cleanup checklist, and tests

Excluded intentionally from clean release packages:
- Git metadata: `.git`
- local assistant/tooling metadata: `.claude`
- Python caches: `__pycache__`, `*.pyc`
- test/tool caches: `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
- desktop run logs: `DesktopApp\RunLogs`
- generated logs: `*.log`
- desktop local state snapshots: `*.state.json`
- accumulated pipeline config backups: `*.backup_*.psd1`

The V4 working folder may still accumulate generated logs, local state, config backups, and bytecode caches during development or real operation. Use the root release builder to create a scrubbed new-user copy:

```powershell
.\Build-MediaPipelineRemuxEncodeAIO-Release.ps1 -Zip
```

V3 was left intact during migration so V4 can be validated before any destructive cleanup, archive, or deletion of old files.
