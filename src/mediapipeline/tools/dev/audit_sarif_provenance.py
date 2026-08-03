"""Lock Audit SARIF ruleset bytes and embed reproducible scanner provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO, Callable, ContextManager

import yaml


PROVENANCE_PROPERTY = "mediaPipelineAuditProvenance"
RULESET_DIGEST_KIND = "canonical-json-sorted-rules-v1"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class RulesetEvidence:
    source: str
    semantic_sha256: str
    raw_sha256: str
    rule_count: int
    bytes_written: int


@dataclass(frozen=True)
class SarifProvenance:
    scanner: str
    scanner_version: str
    ruleset_source: str | None = None
    ruleset_sha256: str | None = None
    ruleset_digest_kind: str | None = None


@dataclass(frozen=True)
class SarifDigest:
    sha256: str
    run_count: int
    finding_count: int
    provenance: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class SarifComparisonEntry:
    path: str
    sha256: str
    run_count: int
    finding_count: int
    provenance: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class SarifComparison:
    ok: bool
    entries: tuple[SarifComparisonEntry, ...]
    errors: tuple[str, ...]


UrlOpener = Callable[..., ContextManager[BinaryIO]]


def _normalized_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if not SHA256_PATTERN.fullmatch(normalized):
        raise ValueError("expected SHA-256 must be exactly 64 lowercase hexadecimal characters")
    return normalized


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def ruleset_semantic_digest(content: bytes) -> tuple[str, int]:
    payload = yaml.safe_load(content)
    if not isinstance(payload, dict) or set(payload) != {"rules"}:
        raise ValueError("downloaded ruleset must contain only a rules array")
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("downloaded ruleset rules must be a non-empty array")
    rule_ids: list[str] = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("each downloaded rule must be an object")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("each downloaded rule must have a non-empty string id")
        rule_ids.append(rule_id)
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("downloaded ruleset contains duplicate rule ids")
    canonical = json.dumps(
        {"rules": sorted(rules, key=lambda rule: rule["id"])},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest(), len(rules)


def fetch_pinned_ruleset(
    *,
    source: str,
    expected_semantic_sha256: str,
    output: Path,
    opener: UrlOpener = urllib.request.urlopen,
) -> RulesetEvidence:
    expected = _normalized_sha256(expected_semantic_sha256)
    request = urllib.request.Request(
        source,
        headers={
            "Accept-Encoding": "identity",
            "User-Agent": "MediaPipeline-Audit-SARIF/1",
        },
    )
    with opener(request, timeout=60) as response:
        content = response.read()
    raw_sha256 = hashlib.sha256(content).hexdigest()
    semantic_sha256, rule_count = ruleset_semantic_digest(content)
    if semantic_sha256 != expected:
        raise ValueError(
            "downloaded ruleset semantic SHA-256 mismatch: "
            f"expected {expected}, resolved {semantic_sha256} "
            f"(raw SHA-256 {raw_sha256})"
        )
    if not content.strip():
        raise ValueError("downloaded ruleset is empty")
    _atomic_write_bytes(output, content)
    return RulesetEvidence(
        source=source,
        semantic_sha256=semantic_sha256,
        raw_sha256=raw_sha256,
        rule_count=rule_count,
        bytes_written=len(content),
    )


def _scanner_version(run: dict[str, Any], *, scanner: str) -> str:
    tool = run.get("tool")
    driver = tool.get("driver") if isinstance(tool, dict) else None
    if not isinstance(driver, dict):
        raise ValueError("SARIF run is missing tool.driver provenance")
    driver_name = str(driver.get("name", ""))
    if scanner.casefold() not in driver_name.casefold():
        raise ValueError(
            f"SARIF driver {driver_name!r} does not identify scanner {scanner!r}"
        )
    version = str(driver.get("semanticVersion") or driver.get("version") or "")
    if not version:
        raise ValueError("SARIF tool.driver does not record a scanner version")
    return version


def stamp_sarif_provenance(
    *,
    sarif: Path,
    scanner: str,
    expected_version: str,
    ruleset_source: str | None = None,
    ruleset_sha256: str | None = None,
    ruleset_digest_kind: str | None = None,
) -> SarifProvenance:
    ruleset_fields = (ruleset_source, ruleset_sha256, ruleset_digest_kind)
    if any(value is None for value in ruleset_fields) and any(
        value is not None for value in ruleset_fields
    ):
        raise ValueError(
            "ruleset source, SHA-256, and digest kind must be supplied together"
        )
    normalized_ruleset_sha = (
        _normalized_sha256(ruleset_sha256) if ruleset_sha256 is not None else None
    )
    payload = json.loads(sarif.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != "2.1.0":
        raise ValueError("SARIF root must be an object with version 2.1.0")
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("SARIF runs must be a non-empty array")

    provenance = SarifProvenance(
        scanner=scanner,
        scanner_version=expected_version,
        ruleset_source=ruleset_source,
        ruleset_sha256=normalized_ruleset_sha,
        ruleset_digest_kind=ruleset_digest_kind,
    )
    serialized = {
        key: value
        for key, value in asdict(provenance).items()
        if value is not None
    }
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("each SARIF run must be an object")
        actual_version = _scanner_version(run, scanner=scanner)
        if actual_version != expected_version:
            raise ValueError(
                f"SARIF scanner version mismatch for {scanner}: "
                f"expected {expected_version}, resolved {actual_version}"
            )
        properties = run.setdefault("properties", {})
        if not isinstance(properties, dict):
            raise ValueError("SARIF run properties must be an object")
        properties[PROVENANCE_PROPERTY] = serialized

    _atomic_write_bytes(
        sarif,
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return provenance


def normalized_sarif_digest(sarif: Path) -> SarifDigest:
    payload = json.loads(sarif.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != "2.1.0":
        raise ValueError("SARIF root must be an object with version 2.1.0")
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("SARIF runs must be a non-empty array")
    finding_count = 0
    provenance: list[dict[str, str]] = []
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("each SARIF run must be an object")
        results = run.get("results", [])
        if not isinstance(results, list):
            raise ValueError("each SARIF run results value must be an array")
        finding_count += len(results)
        properties = run.get("properties")
        evidence = properties.get(PROVENANCE_PROPERTY) if isinstance(properties, dict) else None
        if not isinstance(evidence, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in evidence.items()
        ):
            raise ValueError(
                f"each SARIF run must contain string-valued {PROVENANCE_PROPERTY}"
            )
        provenance.append(dict(sorted(evidence.items())))
    normalized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return SarifDigest(
        sha256=hashlib.sha256(normalized).hexdigest(),
        run_count=len(runs),
        finding_count=finding_count,
        provenance=tuple(provenance),
    )


def compare_sarif_evidence(paths: tuple[Path, ...]) -> SarifComparison:
    if len(paths) < 2:
        raise ValueError("at least two SARIF files are required for comparison")
    entries = tuple(
        SarifComparisonEntry(path=str(path), **asdict(normalized_sarif_digest(path)))
        for path in paths
    )
    baseline = entries[0]
    errors: list[str] = []
    for entry in entries[1:]:
        if entry.provenance != baseline.provenance:
            errors.append(
                f"SARIF provenance mismatch: {baseline.path} != {entry.path}"
            )
        if entry.sha256 != baseline.sha256:
            errors.append(
                "normalized SARIF digest mismatch: "
                f"{baseline.path}={baseline.sha256}, {entry.path}={entry.sha256}"
            )
    return SarifComparison(
        ok=not errors,
        entries=entries,
        errors=tuple(errors),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch-ruleset")
    fetch.add_argument("--source", required=True)
    fetch.add_argument("--semantic-sha256", required=True)
    fetch.add_argument("--output", type=Path, required=True)

    stamp = subparsers.add_parser("stamp-sarif")
    stamp.add_argument("--sarif", type=Path, required=True)
    stamp.add_argument("--scanner", required=True)
    stamp.add_argument("--expected-version", required=True)
    stamp.add_argument("--ruleset-source")
    stamp.add_argument("--ruleset-sha256")
    stamp.add_argument("--ruleset-digest-kind")

    digest = subparsers.add_parser("digest-sarif")
    digest.add_argument("--sarif", type=Path, required=True)

    compare = subparsers.add_parser("compare-sarif")
    compare.add_argument("--sarif", type=Path, action="append", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "fetch-ruleset":
            evidence: RulesetEvidence | SarifProvenance | SarifDigest | SarifComparison = fetch_pinned_ruleset(
                source=args.source,
                expected_semantic_sha256=args.semantic_sha256,
                output=args.output,
            )
        elif args.command == "stamp-sarif":
            evidence = stamp_sarif_provenance(
                sarif=args.sarif,
                scanner=args.scanner,
                expected_version=args.expected_version,
                ruleset_source=args.ruleset_source,
                ruleset_sha256=args.ruleset_sha256,
                ruleset_digest_kind=args.ruleset_digest_kind,
            )
        elif args.command == "digest-sarif":
            evidence = normalized_sarif_digest(args.sarif)
        else:
            evidence = compare_sarif_evidence(tuple(args.sarif))
    except (
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
        yaml.YAMLError,
    ) as exc:
        print(f"Audit SARIF provenance failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(evidence), indent=2))
    return 0 if not isinstance(evidence, SarifComparison) or evidence.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PROVENANCE_PROPERTY",
    "RULESET_DIGEST_KIND",
    "RulesetEvidence",
    "SarifComparison",
    "SarifComparisonEntry",
    "SarifDigest",
    "SarifProvenance",
    "compare_sarif_evidence",
    "fetch_pinned_ruleset",
    "main",
    "normalized_sarif_digest",
    "ruleset_semantic_digest",
    "stamp_sarif_provenance",
]
