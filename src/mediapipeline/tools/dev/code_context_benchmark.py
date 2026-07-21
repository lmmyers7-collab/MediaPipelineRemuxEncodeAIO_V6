"""Measure deterministic code-context retrieval quality, tokens, and latency."""

from __future__ import annotations

import argparse
import json
import math
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

from mediapipeline.tools.dev.code_context_service import CodeContextService
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "code_context_retrieval_cases.v1.json"
EXPECTED_SCHEMA = "mediapipeline_code_retrieval_cases.v1"
EXPECTED_CASE_COUNT = 48
SEARCH_LATENCY_QUERIES = (
    "close_readiness",
    "strict_json",
    "queue snapshot",
    "encode_policy",
    "ass_to_srt",
    "pending_manifest",
    "rename preview",
    "network coordinator",
)


def _percentile(values: Iterable[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * percentile) - 1))
    return round(ordered[index], 3)


def load_cases(path: Path = DEFAULT_FIXTURE) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        raise ValueError(f"unsupported retrieval fixture schema: {payload.get('schema_version')}")
    cases: list[dict[str, Any]] = []
    ids: set[str] = set()
    for group in payload.get("groups", ()):
        shared = {key: value for key, value in group.items() if key not in {"id", "tasks"}}
        for task in group.get("tasks", ()):
            case_id = str(task["id"])
            if case_id in ids:
                raise ValueError(f"duplicate retrieval case id: {case_id}")
            ids.add(case_id)
            cases.append({"group": group["id"], **shared, **task})
    if len(cases) != EXPECTED_CASE_COUNT:
        raise ValueError(f"expected {EXPECTED_CASE_COUNT} retrieval cases, found {len(cases)}")
    for case in cases:
        for key in ("authority_paths", "expected_test_paths", "boundary_paths"):
            for relative in case[key]:
                if not (REPO_ROOT / relative).is_file():
                    raise ValueError(f"retrieval fixture references a missing path: {relative}")
    return cases


def _is_relevant(service: CodeContextService, path: str, case: dict[str, Any]) -> bool:
    expected_paths = {
        *case["authority_paths"],
        *case["expected_test_paths"],
        *case["boundary_paths"],
    }
    if path in expected_paths:
        return True
    record = service.records_by_path.get(path)
    if not record:
        return False
    expected_features = set(case["expected_features"])
    return record.feature_group in expected_features or bool(expected_features.intersection(record.feature_groups))


def _benchmark_reload(index_path: Path) -> float:
    with tempfile.TemporaryDirectory() as tempdir:
        temporary_index = Path(tempdir) / "PROJECT_INDEX.jsonl"
        raw = index_path.read_bytes()
        temporary_index.write_bytes(raw)
        service = CodeContextService(root=REPO_ROOT, index_path=temporary_index)
        temporary_index.write_bytes(raw + b"\n")
        started = time.perf_counter()
        result = service.code_lookup("src/mediapipeline/tools/dev/code_context_service.py")
        elapsed = (time.perf_counter() - started) * 1000
        if not result.get("ok"):
            raise RuntimeError(f"reload benchmark failed: {result}")
        return elapsed


def run_benchmark(
    *,
    fixture_path: Path = DEFAULT_FIXTURE,
    index_path: Path | None = None,
    budget: int = 2000,
) -> dict[str, Any]:
    cases = load_cases(fixture_path)
    service = CodeContextService(root=REPO_ROOT, index_path=index_path)
    context_latencies: list[float] = []
    response_tokens: list[float] = []
    reciprocal_ranks: list[float] = []
    recall5_hits = 0
    recall10_hits = 0
    required_layer_hits = 0
    required_layer_total = 0
    irrelevant = 0
    considered = 0
    high_risk_total = 0
    high_risk_test_hits = 0
    high_risk_boundary_hits = 0
    case_results: list[dict[str, Any]] = []

    # The acceptance target is explicitly for warm repo_context calls. Populate
    # the revision-aware LRU first, then measure the same representative tasks.
    for case in cases:
        warm_result = service.repo_context(case["task"], budget=budget)
        if not warm_result.get("ok"):
            raise RuntimeError(f"retrieval warmup failed for {case['id']}: {warm_result}")

    for case in cases:
        started = time.perf_counter()
        result = service.repo_context(case["task"], budget=budget)
        context_latencies.append((time.perf_counter() - started) * 1000)
        if not result.get("ok"):
            raise RuntimeError(f"retrieval failed for {case['id']}: {result}")
        response_tokens.append(float(result["estimated_tokens"]))
        paths = [item["path"] for item in result.get("items", ())]
        authority_ranks = [paths.index(path) + 1 for path in case["authority_paths"] if path in paths]
        best_rank = min(authority_ranks, default=0)
        if best_rank and best_rank <= 5:
            recall5_hits += 1
        if best_rank and best_rank <= 10:
            recall10_hits += 1
        reciprocal_ranks.append(1.0 / best_rank if best_rank else 0.0)
        layers = {item["layer"] for item in result.get("items", ())}
        required_layer_hits += len(layers.intersection(case["required_layers"]))
        required_layer_total += len(case["required_layers"])
        for path in paths[:10]:
            considered += 1
            if not _is_relevant(service, path, case):
                irrelevant += 1
        related_tests = {
            test_path
            for item in result.get("items", ())
            for test_path in item.get("tests", ())
        }
        expected_test_hit = any(path in paths or path in related_tests for path in case["expected_test_paths"])
        selected_test_hit = any(
            service.records_by_path.get(path) and service.records_by_path[path].evidence_category == "test"
            for path in paths
        )
        test_hit = selected_test_hit or bool(related_tests)
        boundary_hit = any(path in paths for path in case["boundary_paths"])
        if case["high_risk"]:
            high_risk_total += 1
            high_risk_test_hits += int(test_hit)
            high_risk_boundary_hits += int(boundary_hit)
        case_results.append(
            {
                "id": case["id"],
                "authority_rank": best_rank or None,
                "test_hit": test_hit,
                "expected_test_hit": expected_test_hit,
                "boundary_hit": boundary_hit,
                "returned": len(paths),
                "top_paths": paths[:10],
            }
        )

    search_latencies: list[float] = []
    for query in SEARCH_LATENCY_QUERIES:
        started = time.perf_counter()
        result = service.code_search(query, max_results=10)
        search_latencies.append((time.perf_counter() - started) * 1000)
        if not result.get("ok"):
            raise RuntimeError(f"search benchmark failed for {query}: {result}")

    case_count = len(cases)
    return {
        "schema_version": "mediapipeline_code_context_benchmark.v1",
        "fixture_schema": EXPECTED_SCHEMA,
        "case_count": case_count,
        "index_revision": service.index_revision,
        "quality": {
            "authority_recall_at_5": round(recall5_hits / case_count, 4),
            "authority_recall_at_10": round(recall10_hits / case_count, 4),
            "mean_reciprocal_rank": round(sum(reciprocal_ranks) / case_count, 4),
            "vertical_slice_completeness": round(required_layer_hits / max(1, required_layer_total), 4),
            "irrelevant_top_10_rate": round(irrelevant / max(1, considered), 4),
            "high_risk_test_coverage": round(high_risk_test_hits / max(1, high_risk_total), 4),
            "high_risk_boundary_coverage": round(high_risk_boundary_hits / max(1, high_risk_total), 4),
        },
        "tokens": {
            "mean": round(sum(response_tokens) / case_count, 2),
            "p95": _percentile(response_tokens, 0.95),
            "max": max(response_tokens, default=0),
        },
        "latency_ms": {
            "repo_context_p50": _percentile(context_latencies, 0.50),
            "repo_context_p95": _percentile(context_latencies, 0.95),
            "code_search_p50": _percentile(search_latencies, 0.50),
            "code_search_p95": _percentile(search_latencies, 0.95),
            "index_reload": round(_benchmark_reload(index_path or service.index_path), 3),
        },
        "cases": case_results,
    }


def acceptance_findings(payload: dict[str, Any]) -> list[str]:
    quality = payload["quality"]
    latency = payload["latency_ms"]
    findings: list[str] = []
    thresholds = (
        (quality["authority_recall_at_5"] >= 0.90, "authority Recall@5 is below 90%"),
        (quality["authority_recall_at_10"] >= 0.97, "authority Recall@10 is below 97%"),
        (quality["irrelevant_top_10_rate"] <= 0.20, "irrelevant top-10 rate exceeds 20%"),
        (quality["high_risk_test_coverage"] == 1.0, "a high-risk case omitted its expected test"),
        (quality["high_risk_boundary_coverage"] == 1.0, "a high-risk case omitted its boundary document"),
        (latency["repo_context_p95"] <= 50, "repo_context p95 exceeds 50 ms"),
        (latency["code_search_p95"] <= 300, "code_search p95 exceeds 300 ms"),
        (latency["index_reload"] <= 250, "index reload exceeds 250 ms"),
    )
    findings.extend(message for passed, message in thresholds if not passed)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--budget", type=int, default=2000)
    parser.add_argument("--check", action="store_true", help="Fail when the Release 1 acceptance thresholds are missed.")
    args = parser.parse_args(argv)
    payload = run_benchmark(fixture_path=args.fixture, index_path=args.index, budget=args.budget)
    findings = acceptance_findings(payload)
    payload["acceptance"] = {"passed": not findings, "findings": findings}
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.check and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["acceptance_findings", "load_cases", "main", "run_benchmark"]
