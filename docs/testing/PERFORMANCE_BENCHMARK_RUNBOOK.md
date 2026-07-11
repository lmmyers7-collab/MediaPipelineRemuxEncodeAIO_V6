# Performance Benchmark Runbook

Use the bundled Python runtime to capture repeatable, read-only baselines before
and after performance changes:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
  mediapipeline.tools.dev.performance_benchmark `
  --repeat 5 `
  --variant baseline `
  --ledger .\LocalBase\State\Performance\performance_benchmark.jsonl
```

The default run measures backend import wall time, backend-served WebView script
inventory, and the PowerShell pipeline module graph. It does not start the API,
open the WebView, process media, scan source roots, run ffprobe, publish output,
or mutate queue/media state. A ledger is written only when `--ledger` is given.

To time one existing developer audit suite, add `--audit-suite`:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
  mediapipeline.tools.dev.performance_benchmark `
  --repeat 5 `
  --audit-suite phase1-generated `
  --variant baseline
```

Audit suites run up to four independent read-only checks concurrently by
default while preserving manifest/report order. Use `--jobs 1` for a sequential
comparison or `--jobs 1..8` to measure a bounded candidate directly:

```powershell
.\apps\desktop\runtime\Python\python.exe -m mediapipeline.tools.dev.audit_checks `
  run phase1-generated --jobs 4
```

Compare candidates using the same machine, input tree, repeat count, timeout,
and correctness gate. Promote a candidate only when all benchmark operations
remain correct and the improvement repeats outside normal measurement noise.

For media-processing changes, this benchmark is supporting evidence only. The
validation ladder and representative real-media validation remain required;
startup/import measurements never replace output correctness proof.
