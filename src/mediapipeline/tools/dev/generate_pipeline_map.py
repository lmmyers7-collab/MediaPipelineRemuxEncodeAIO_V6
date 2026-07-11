"""Generate docs/generated/PIPELINE_MAP.md from mediapipeline.contracts.stages.

The stage registry in src/mediapipeline/contracts/stages.py is the source for stage
order, stage wire name, payload class, result class, Pydantic field lists,
and initial entrypoint enablement. This script adds static operator notes
for each known stage so the generated Markdown stays useful without
letting the contract table drift.
"""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import sys
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import ModuleType
from typing import Any

REPO_ROOT = find_repo_root(Path(__file__))
STAGES_PATH = REPO_ROOT / "src" / "mediapipeline" / "contracts" / "stages.py"
GENERATED_DOCS_ROOT = REPO_ROOT / "docs" / "generated"
PIPELINE_MAP_PATH = GENERATED_DOCS_ROOT / "PIPELINE_MAP.md"

STAGE_METADATA: dict[str, dict[str, object]] = {
    "ingest": {
        "notes": "Source to scratch copy. Returns scratch path, size, and sha256.",
        "domains": "src/mediapipeline/core/orchestration/ (stage boundary), ops/pipeline/engine/storage/ (scratch copy)",
        "detail": [
            "Source files are never mutated.",
            "Scratch copies are hashed before downstream stages consume them.",
        ],
    },
    "probe": {
        "notes": "ffprobe on scratch. Returns container, duration, and stream summaries.",
        "domains": "src/mediapipeline/contracts/source_media*.py (source facts), ops/pipeline/engine/probe/ (ffprobe)",
        "detail": [
            "Probe cache keys are expected to include path, mtime, and size.",
            "Subtitle, audio, attachment, chapter, and data parity checks remain high risk.",
        ],
    },
    "decide": {
        "notes": "Remux vs encode vs skip. Returns route and encoder profile.",
        "domains": "src/mediapipeline/core/decide/",
        "detail": [
            "Decision output is data-only; no FFmpeg args are constructed here.",
            "Routing, ladder, and size policy changes require high validation.",
        ],
    },
    "transcode": {
        "notes": "FFmpeg invocation. Returns output path, size, and attempts.",
        "domains": "src/mediapipeline/core/processes/ and src/mediapipeline/core/orchestration/ (runner/plans), ops/pipeline/engine/process/ and ops/pipeline/entrypoints/MediaPipeline/ (invocation)",
        "detail": [
            "Descriptive contract only; permanently disabled in the orchestration-only dispatcher.",
            "FFmpeg command generation and stream mapping are high-risk surfaces.",
            "Attempt records preserve encoder, timestamps, exit code, and log path.",
        ],
    },
    "subtitle-convert": {
        "notes": "ASS/TX3G/BDPGS to SRT, language filtering, and review routing.",
        "domains": "src/mediapipeline/contracts/source_media*.py (subtitle facts), ops/pipeline/engine/subtitles/",
        "detail": [
            "Descriptive contract only; permanently disabled in the orchestration-only dispatcher.",
            "Original subtitles are preserved by default.",
            "OCR/conversion failure routes to review, never silent bad publish.",
        ],
    },
    "audio-mix": {
        "notes": "Passthrough, downmix, or transcode by profile.",
        "domains": "src/mediapipeline/contracts/source_media*.py (audio facts), ops/pipeline/engine/audio/",
        "detail": [
            "Descriptive contract only; permanently disabled in the orchestration-only dispatcher.",
            "Audio routing is profile/config driven.",
            "Passthrough, downmix, and transcode policy changes require high validation.",
        ],
    },
    "publish": {
        "notes": "Move to final root, or park on final-root safety guard.",
        "domains": "src/mediapipeline/core/publish/, ops/pipeline/engine/publish/",
        "detail": [
            "Descriptive contract only; permanently disabled in the orchestration-only dispatcher.",
            "Pending publish parks output when final placement is unsafe.",
            "Publish evidence is captured through manifest_path and pending_publish_id.",
        ],
    },
    "drain": {
        "notes": "Drain parked outputs to final root with manifest evidence.",
        "domains": "src/mediapipeline/core/publish/ (drain), ops/pipeline/engine/publish/",
        "detail": [
            "Descriptive contract only; permanently disabled in the orchestration-only dispatcher.",
            "Drain moves only from pending-publish evidence, not from source media.",
            "Retry policy is expected to be conservative because final roots may be unavailable.",
        ],
    },
    "rename": {
        "notes": "Plan, apply, or undo rename operations with sidecars.",
        "domains": "src/mediapipeline/core/rename/, ops/pipeline/engine/naming/",
        "detail": [
            "Descriptive contract only; permanently disabled in the orchestration-only dispatcher.",
            "Backend owns apply and undo behavior.",
            "Every apply is expected to write an undo record.",
        ],
    },
}


def load_stages_module() -> ModuleType:
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    spec = importlib.util.spec_from_file_location("mediapipeline_stage_contracts", STAGES_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load stage contract module at {STAGES_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def stage_value(stage: Any) -> str:
    return getattr(stage, "value", str(stage))


def model_field_names(cls: type, excluded: set[str]) -> list[str]:
    fields = getattr(cls, "model_fields", {})
    return [name for name in fields if name not in excluded]


def code_list(values: list[str]) -> str:
    if not values:
        return "none"
    return ", ".join(f"`{value}`" for value in values)


def table_cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_pipeline_map(module: ModuleType) -> str:
    payload_base_fields = set(getattr(module.StagePayload, "model_fields", {}))
    data_base_fields = set(getattr(module.StageData, "model_fields", {}))
    registry = module.STAGE_REGISTRY

    rows: list[dict[str, object]] = []
    for index, (stage, contract) in enumerate(registry.items(), start=1):
        payload_cls = contract.payload_model
        result_cls = contract.result_model
        name = stage_value(stage)
        metadata = STAGE_METADATA.get(name, {})
        rows.append(
            {
                "index": index,
                "stage": name,
                "payload": payload_cls.__name__,
                "result": result_cls.__name__,
                "payload_fields": model_field_names(payload_cls, payload_base_fields),
                "result_fields": model_field_names(result_cls, data_base_fields),
                "notes": str(metadata.get("notes", "")),
                "domains": str(metadata.get("domains", "n/a")),
                "detail": list(metadata.get("detail", [])),
                "mutation": bool(contract.mutation_capable),
                "enabled": bool(contract.enabled_in_entrypoint),
                "journal_event_type": str(contract.journal_event_type),
            }
        )

    lines: list[str] = []
    lines.append("# Pipeline map")
    lines.append("")
    lines.append("Generated by `python -m mediapipeline.tools.dev.generate_pipeline_map` from `src/mediapipeline/contracts/stages.py`. Do not hand-edit.")
    lines.append("")
    lines.append("This file enumerates the canonical pipeline stages, their payload/data contracts,")
    lines.append("stage-specific Pydantic fields, and the intended Python/PowerShell ownership")
    lines.append("surface per ADR-0002.")
    lines.append("")
    lines.append("## Wire contract")
    lines.append("")
    lines.append("Every stage runs via:")
    lines.append("")
    lines.append("```")
    lines.append("ops/pipeline/engine/entrypoint.ps1 -Stage <stage> -PayloadJson <json-or-path>")
    lines.append("```")
    lines.append("")
    lines.append("- `<stage>` is a value from `src/mediapipeline/contracts/stages.py::StageName`.")
    lines.append("- `<payload-json>` is a `StageRequest` envelope or a path to a JSON file.")
    lines.append("- The engine returns a `StageResult` envelope on stdout as one JSON document.")
    lines.append("- Logs go to stderr and must not be required for result parsing.")
    lines.append(f"- All payloads and results carry `schema_version: \"{module.STAGE_SCHEMA_VERSION}\"`.")
    lines.append("- The engine rejects unknown schema versions.")
    lines.append("- The dispatcher is orchestration-only; no Local API stage-execute route exists.")
    lines.append("- Only stages marked enabled below dispatch to behavior; disabled mutation DTOs are descriptive contracts, not future route commitments.")
    lines.append("")
    lines.append("## Stages")
    lines.append("")
    lines.append("| # | Stage | Enabled | Mutation | Payload | Data | Payload fields | Data fields | Notes |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        lines.append(
            "| {index} | `{stage}` | {enabled} | {mutation} | `{payload}` | `{result}` | {payload_fields} | {result_fields} | {notes} |".format(
                index=row["index"],
                stage=row["stage"],
                enabled="yes" if row["enabled"] else "no",
                mutation="yes" if row["mutation"] else "no",
                payload=row["payload"],
                result=row["result"],
                payload_fields=table_cell(code_list(row["payload_fields"])),
                result_fields=table_cell(code_list(row["result_fields"])),
                notes=table_cell(str(row["notes"])),
            )
        )
    lines.append("")
    lines.append("## Per-stage detail")
    lines.append("")
    for row in rows:
        lines.append(f"### {row['index']}. {row['stage']}")
        lines.append("")
        lines.append(f"- **Payload:** `{row['payload']}`")
        lines.append(f"- **Data:** `{row['result']}`")
        lines.append(f"- **Entrypoint enabled:** {'yes' if row['enabled'] else 'no'}")
        lines.append(f"- **Mutation capable:** {'yes' if row['mutation'] else 'no'}")
        lines.append(f"- **Journal event type:** `{row['journal_event_type']}`")
        lines.append(f"- **Payload fields:** {code_list(row['payload_fields'])}")
        lines.append(f"- **Data fields:** {code_list(row['result_fields'])}")
        lines.append(f"- **Domain:** {row['domains']}")
        for item in row["detail"]:
            lines.append(f"- **Note:** {item}")
        lines.append("")
    lines.append("## Schemas")
    lines.append("")
    lines.append("`src/mediapipeline/contracts/schemas/stages.v1.schema.json` is generated from `src/mediapipeline/contracts/stages.py`.")
    lines.append("")
    lines.append("## Validation")
    lines.append("")
    lines.append("- `src/mediapipeline/contracts/stages.py::STAGE_REGISTRY` must match this generated table.")
    lines.append("- `python -m mediapipeline.tools.dev.generate_pipeline_map --check` fails when this file drifts.")
    lines.append("- `python -m mediapipeline.tools.dev.generate_stage_schema --check` fails when the schema drifts.")
    lines.append("- Contract tests validate every stage payload/data model.")
    lines.append("")
    return "\n".join(lines)


def check_file(expected: str) -> bool:
    if not PIPELINE_MAP_PATH.exists():
        print(f"Missing generated file: {PIPELINE_MAP_PATH.relative_to(REPO_ROOT)}")
        return False
    actual = PIPELINE_MAP_PATH.read_text(encoding="utf-8", errors="replace")
    if actual == expected:
        print(f"OK: {PIPELINE_MAP_PATH.relative_to(REPO_ROOT)} is current.")
        return True
    rel = PIPELINE_MAP_PATH.relative_to(REPO_ROOT)
    print(f"{rel} is stale. Run: python -m mediapipeline.tools.dev.generate_pipeline_map")
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=f"{rel} (current)",
        tofile=f"{rel} (expected)",
        lineterm="",
    )
    for line in list(diff)[:160]:
        print(line)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify docs/generated/PIPELINE_MAP.md without rewriting.",
    )
    args = parser.parse_args(argv)

    expected = render_pipeline_map(load_stages_module())
    if args.check:
        return 0 if check_file(expected) else 1

    GENERATED_DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    PIPELINE_MAP_PATH.write_text(expected, encoding="utf-8")
    print(f"Wrote {PIPELINE_MAP_PATH.relative_to(REPO_ROOT)} from src/mediapipeline/contracts/stages.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
