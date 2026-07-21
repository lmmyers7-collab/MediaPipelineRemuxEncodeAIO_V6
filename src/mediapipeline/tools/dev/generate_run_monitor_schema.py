"""Generate canonical and PowerShell Run Monitor JSON Schemas.

Use ``--check`` in CI/pre-commit to fail when either generated schema is stale.
"""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
CANONICAL_SCHEMA_PATH = REPO_ROOT / "src" / "mediapipeline" / "contracts" / "schemas" / "run_monitor.v1.schema.json"
PIPELINE_SCHEMA_PATH = REPO_ROOT / "ops" / "pipeline" / "config" / "schemas" / "media_pipeline_run_monitor.schema.json"


def render_schema(*, schema_id: str) -> str:
    from mediapipeline.contracts.run_monitor import RUN_MONITOR_SCHEMA_VERSION, RunMonitorRecord

    schema = RunMonitorRecord.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = schema_id
    schema["title"] = "MediaPipeline Run Once Monitor"
    schema["x-run-monitor-schema-version"] = RUN_MONITOR_SCHEMA_VERSION
    return json.dumps(schema, indent=2) + "\n"


def _expected_outputs() -> dict[Path, str]:
    return {
        CANONICAL_SCHEMA_PATH: render_schema(
            schema_id="https://local.mediapipeline/src/mediapipeline/contracts/schemas/run_monitor.v1.schema.json"
        ),
        PIPELINE_SCHEMA_PATH: render_schema(
            schema_id="https://local.mediapipeline/ops/pipeline/config/schemas/media_pipeline_run_monitor.schema.json"
        ),
    }


def _write_if_changed(path: Path, text: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def _check_current(path: Path, expected: str) -> bool:
    actual = path.read_text(encoding="utf-8") if path.exists() else ""
    if actual == expected:
        print(f"OK: {path.relative_to(REPO_ROOT)} is current")
        return True
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=str(path.relative_to(REPO_ROOT)),
        tofile=f"{path.relative_to(REPO_ROOT)} (generated)",
        lineterm="",
    )
    print(f"Run Monitor schema drift detected for {path.relative_to(REPO_ROOT)}. Regenerate with:")
    print("  python -m mediapipeline.tools.dev.generate_run_monitor_schema")
    print("\n".join(diff))
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if a generated schema is stale")
    args = parser.parse_args(argv)
    outputs = _expected_outputs()
    if args.check:
        return 0 if all(_check_current(path, text) for path, text in outputs.items()) else 1
    for path, expected in outputs.items():
        changed = _write_if_changed(path, expected)
        print(f"{path.relative_to(REPO_ROOT)} {'updated' if changed else 'current'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
