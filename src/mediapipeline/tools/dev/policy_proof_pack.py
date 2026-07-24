"""Build and verify an isolated, owned-media policy proof pack.

The checked-in catalog names logical fixtures and expected media facts.  The
external fixture root owns the local source mapping, media files, and all run
evidence so neither machine paths nor media assets enter Git.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from collections import Counter
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping

from mediapipeline.contracts.source_media_streams import bit_depth as source_bit_depth
from mediapipeline.tools.dev import tdarr_matrix_audit
from mediapipeline.tools.dev import materialize_tdarr_test_library as materializer
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
CATALOG_SCHEMA = "media_policy_proof_catalog.v1"
SOURCE_MAPPING_SCHEMA = "media_policy_proof_sources.v1"
SOURCE_MAPPING_NAME = "policy_proof_sources.json"
RUN_SENTINEL = ".policy-proof-run.json"
REPORT_NAME = "policy_proof_report.json"
REPORT_MARKDOWN_NAME = "policy_proof_report.md"
REPORT_CSV_NAME = "policy_proof_report.csv"
DEFAULT_CATALOG = REPO_ROOT / "tests" / "fixtures" / "media_policy" / "policy_proof_catalog.json"
DEFAULT_FIXTURE_ROOT = Path("E:/Videos/TdarrMatrix/PolicyProofPack")
DEFAULT_FFPROBE = REPO_ROOT / "ops" / "pipeline" / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"

ProbeSource = Callable[[Path], dict[str, Any]]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def assert_allowed_policy_root(path: Path, *, allowed_root: Path = DEFAULT_FIXTURE_ROOT) -> Path:
    resolved = path.resolve(strict=False)
    expected = allowed_root.resolve(strict=False)
    if resolved != expected:
        raise ValueError(f"Policy fixture root must be exactly {expected}")
    return resolved


def safe_relative_path(value: object, *, field_name: str) -> Path:
    text = str(value or "").replace("\\", "/").strip()
    candidate = PurePosixPath(text)
    windows = PureWindowsPath(text)
    if not text or candidate.is_absolute() or windows.is_absolute() or windows.drive or ".." in candidate.parts:
        raise ValueError(f"{field_name} must be a non-empty fixture-root-relative path")
    return Path(*candidate.parts)


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Missing {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label} JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def load_catalog(catalog_path: Path) -> list[dict[str, Any]]:
    payload = load_json_object(catalog_path, label="policy proof catalog")
    if payload.get("schema_version") != CATALOG_SCHEMA:
        raise ValueError(f"Unsupported policy proof catalog schema: {payload.get('schema_version')!r}")
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("Policy proof catalog must contain a non-empty fixtures list")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw in fixtures:
        if not isinstance(raw, dict):
            raise ValueError("Every policy proof fixture must be an object")
        fixture = dict(raw)
        fixture_id = str(fixture.get("id") or "").strip()
        source_key = str(fixture.get("source_key") or "").strip()
        expected_hash = str(fixture.get("sha256") or "").strip().casefold()
        if not fixture_id or not source_key:
            raise ValueError("Every policy proof fixture requires id and source_key")
        if fixture_id in seen:
            raise ValueError(f"Duplicate policy proof fixture id: {fixture_id}")
        if len(expected_hash) != 64 or any(char not in "0123456789abcdef" for char in expected_hash):
            raise ValueError(f"Policy proof fixture {fixture_id} requires a concrete SHA-256")
        if not isinstance(fixture.get("source_facts"), dict):
            raise ValueError(f"Policy proof fixture {fixture_id} requires source_facts")
        if not isinstance(fixture.get("expectations"), dict):
            raise ValueError(f"Policy proof fixture {fixture_id} requires expectations")
        fixture["id"] = fixture_id
        fixture["source_key"] = source_key
        fixture["sha256"] = expected_hash
        seen.add(fixture_id)
        normalized.append(fixture)
    return normalized


def load_source_mapping(fixture_root: Path, *, allowed_root: Path = DEFAULT_FIXTURE_ROOT) -> dict[str, Path]:
    root = assert_allowed_policy_root(fixture_root, allowed_root=allowed_root)
    payload = load_json_object(root / SOURCE_MAPPING_NAME, label="policy proof source mapping")
    if payload.get("schema_version") != SOURCE_MAPPING_SCHEMA:
        raise ValueError(f"Unsupported policy proof source mapping schema: {payload.get('schema_version')!r}")
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("Policy proof source mapping requires a sources object")
    resolved: dict[str, Path] = {}
    for key, raw_path in sources.items():
        relative = safe_relative_path(raw_path, field_name=f"sources.{key}")
        path = (root / relative).resolve(strict=False)
        if not is_under(path, root):
            raise ValueError(f"Source mapping for {key} resolves outside fixture root")
        resolved[str(key)] = path
    return resolved


def _is_attached_picture(stream: Mapping[str, Any]) -> bool:
    disposition = stream.get("disposition")
    if not isinstance(disposition, Mapping):
        return False
    return str(disposition.get("attached_pic") or "").casefold() in {"1", "true"}


def _primary_video_streams(streams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        stream
        for stream in streams
        if stream.get("codec_type") == "video" and not _is_attached_picture(stream)
    ]


def _has_hdr10plus_side_data(row: Mapping[str, Any]) -> bool:
    entries = row.get("side_data_list")
    if not isinstance(entries, list):
        return False
    side_data = " ".join(
        str(item.get("side_data_type") or "") for item in entries if isinstance(item, Mapping)
    ).casefold()
    return "hdr10+" in side_data or "smpte2094-40" in side_data


def _stream_index_key(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    if not text.isdigit():
        return ""
    return str(int(text))


def facts_from_ffprobe_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the stream dimensions that the policy catalog is allowed to assert."""
    streams = [stream for stream in payload.get("streams", []) if isinstance(stream, dict)]
    counts = Counter(str(stream.get("codec_type") or "") for stream in streams)
    subtitles = sorted({str(stream.get("codec_name") or "") for stream in streams if stream.get("codec_type") == "subtitle"})
    audio_languages = sorted(
        {
            str((stream.get("tags") or {}).get("language") or "und")
            for stream in streams
            if stream.get("codec_type") == "audio"
        }
    )
    video_streams = _primary_video_streams(streams)
    transfers = {str(stream.get("color_transfer") or "").casefold() for stream in video_streams}
    stream_side_data_entries = [
        item
        for stream in video_streams
        for item in (stream.get("side_data_list") or [])
        if isinstance(item, dict)
    ]
    stream_hdr10plus = any(
        str(stream.get("color_transfer") or "").casefold() == "smpte2084"
        and _has_hdr10plus_side_data(stream)
        for stream in video_streams
    )
    pq_stream_indexes = {
        index
        for stream in video_streams
        if (index := _stream_index_key(stream.get("index")))
        and str(stream.get("color_transfer") or "").casefold() == "smpte2084"
    }
    frame_hdr10plus = any(
        _has_hdr10plus_side_data(frame)
        and (
            (len(video_streams) == 1 and "smpte2084" in transfers)
            or _stream_index_key(frame.get("stream_index")) in pq_stream_indexes
        )
        for frame in payload.get("frames", [])
        if isinstance(frame, dict)
    )
    hdr = ""
    if stream_hdr10plus or frame_hdr10plus:
        hdr = "hdr10plus"
    elif "arib-std-b67" in transfers:
        hdr = "hlg"
    elif "smpte2084" in transfers:
        hdr = "hdr10"
    dovi_profile = ""
    for entry in stream_side_data_entries:
        if "dovi" not in str(entry.get("side_data_type") or "").casefold() and "dolby vision" not in str(entry.get("side_data_type") or "").casefold():
            continue
        profile = str(entry.get("dv_profile") or "").strip()
        compatibility = str(entry.get("dv_bl_signal_compatibility_id") or "").strip()
        dovi_profile = f"{profile}.{compatibility}" if profile == "8" and compatibility == "1" else profile
        break
    heights = [int(stream["height"]) for stream in video_streams if str(stream.get("height") or "").isdigit()]
    bit_depths = [depth for stream in video_streams if (depth := source_bit_depth(stream)) > 0]
    audio_channels = [int(stream["channels"]) for stream in streams if stream.get("codec_type") == "audio" and str(stream.get("channels") or "").isdigit()]
    interlaced_or_vfr = any(
        str(stream.get("field_order") or "").casefold() not in {"", "progressive", "unknown"}
        or rates_differ(stream.get("r_frame_rate"), stream.get("avg_frame_rate"))
        for stream in video_streams
    )
    return {
        "stream_counts": {key: value for key, value in sorted(counts.items()) if key},
        "subtitle_codecs": subtitles,
        "audio_languages": audio_languages,
        "chapters": bool(payload.get("chapters")),
        "hdr": hdr,
        "dovi_profile": dovi_profile,
        "resolution": f"{max(heights)}p" if heights else "",
        "bit_depth": max(bit_depths) if bit_depths else 0,
        "max_audio_channels": max(audio_channels) if audio_channels else 0,
        "interlaced_or_vfr": interlaced_or_vfr,
    }


def positive_rate(value: object) -> Fraction | None:
    try:
        rate = Fraction(str(value or ""))
    except (ValueError, ZeroDivisionError):
        return None
    return rate if rate > 0 else None


def rates_differ(real_rate: object, average_rate: object) -> bool:
    normalized_real = positive_rate(real_rate)
    normalized_average = positive_rate(average_rate)
    return normalized_real is not None and normalized_average is not None and normalized_real != normalized_average


def run_ffprobe_json(command: list[str], *, path: Path, probe_name: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffprobe is unavailable: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffprobe {probe_name} timed out for {path}") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe {probe_name} failed for {path}: {(completed.stderr or '').strip()[:1000]}")
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe {probe_name} returned invalid JSON for {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"ffprobe {probe_name} returned a non-object payload for {path}")
    return payload


def probe_source_ffprobe(path: Path, *, ffprobe: str = str(DEFAULT_FFPROBE)) -> dict[str, Any]:
    inventory_command = [ffprobe, "-v", "error", "-show_streams", "-show_chapters", "-of", "json", str(path)]
    payload = run_ffprobe_json(inventory_command, path=path, probe_name="inventory probe")
    streams = [stream for stream in payload.get("streams", []) if isinstance(stream, dict)]
    video_streams = _primary_video_streams(streams)
    if any(str(stream.get("color_transfer") or "").casefold() == "smpte2084" for stream in video_streams):
        frame_command = [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "V",
            "-read_intervals",
            "%+#120",
            "-show_frames",
            "-show_entries",
            "frame=stream_index,side_data_list",
            "-of",
            "json",
            str(path),
        ]
        frame_payload = run_ffprobe_json(frame_command, path=path, probe_name="frame metadata probe")
        frame_rows = frame_payload.get("frames")
        if not isinstance(frame_rows, list):
            raise RuntimeError(f"ffprobe frame metadata probe returned invalid frames for {path}")
        frames = [frame for frame in frame_rows if isinstance(frame, dict)]
        if not frames:
            raise RuntimeError(f"ffprobe frame metadata probe returned no video frames for {path}")
        payload["frames"] = frames
    return facts_from_ffprobe_payload(payload)


def facts_match(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if key == "stream_counts" and isinstance(expected_value, Mapping):
            if not isinstance(actual_value, Mapping):
                mismatches.append(key)
                continue
            for stream_type, count in expected_value.items():
                if actual_value.get(stream_type) != count:
                    mismatches.append(f"stream_counts.{stream_type}")
        elif isinstance(expected_value, list):
            actual_values = set(actual_value if isinstance(actual_value, list) else [])
            if not set(expected_value).issubset(actual_values):
                mismatches.append(key)
        elif actual_value != expected_value:
            mismatches.append(key)
    return mismatches


def assert_output_expectations(
    fixture: Mapping[str, Any],
    *,
    output_facts: Mapping[str, Any],
    worker_result: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Compare catalogued output and publish facts without interpreting media policy.

    The pipeline remains the authority for route and publish decisions.  This helper only
    checks the evidence emitted by that authority against the scenario contract.
    """
    expectations = fixture.get("expectations") if isinstance(fixture.get("expectations"), Mapping) else {}
    output_expectations = expectations.get("output") if isinstance(expectations.get("output"), Mapping) else {}
    publish_expectations = expectations.get("publish") if isinstance(expectations.get("publish"), Mapping) else {}
    findings: list[dict[str, str]] = []
    fact_expectations = {key: value for key, value in output_expectations.items() if key not in {"sidecar_kinds", "route_outcome"}}
    mismatches = facts_match(fact_expectations, output_facts)
    if mismatches:
        findings.append({"severity": "error", "code": "output_fact_mismatch", "message": f"Output facts differ: {', '.join(mismatches)}."})
    expected_sidecars = output_expectations.get("sidecar_kinds")
    if isinstance(expected_sidecars, list):
        actual_sidecars = set(worker_result.get("SidecarKinds") if isinstance(worker_result.get("SidecarKinds"), list) else [])
        if not set(expected_sidecars).issubset(actual_sidecars):
            findings.append({"severity": "error", "code": "output_sidecar_mismatch", "message": "Expected output sidecar evidence is missing."})
    route_outcome = output_expectations.get("route_outcome")
    if route_outcome:
        route = str(worker_result.get("Route") or "").casefold()
        reviewed = not bool(worker_result.get("Success")) and bool(worker_result.get("Reason") or worker_result.get("ErrorCode"))
        if route_outcome == "remux_or_review" and not (route == "remux" or reviewed):
            findings.append({"severity": "error", "code": "route_outcome_mismatch", "message": "Fixture neither remuxed nor produced review evidence."})
        elif route_outcome != "remux_or_review" and route != str(route_outcome).casefold():
            findings.append({"severity": "error", "code": "route_outcome_mismatch", "message": "Route outcome differs from catalog."})
    expected_state = publish_expectations.get("terminal_state")
    if expected_state and str(worker_result.get("PublishState") or "").casefold() != str(expected_state).casefold():
        findings.append({"severity": "error", "code": "publish_state_mismatch", "message": "Publish terminal state differs from catalog."})
    if publish_expectations.get("sidecars") is True:
        actual_sidecars = worker_result.get("SidecarKinds")
        if not isinstance(actual_sidecars, list) or not actual_sidecars:
            findings.append({"severity": "error", "code": "publish_sidecar_mismatch", "message": "Publish evidence has no sidecar proof."})
    resilience = fixture.get("resilience") if isinstance(fixture.get("resilience"), Mapping) else {}
    if resilience.get("interrupt_and_rerun") is True and worker_result.get("PolicyProofInterrupted") is not True:
        findings.append({"severity": "error", "code": "interrupt_evidence_missing", "message": "Controlled interruption did not produce timeout evidence before rerun."})
    return findings


def is_applicable(fixture: Mapping[str, Any], effective_config: Mapping[str, Any]) -> bool:
    applicability = fixture.get("applicability")
    if not isinstance(applicability, Mapping):
        return True
    required_config = applicability.get("config")
    if not isinstance(required_config, Mapping):
        return True
    return all(effective_config.get(key) == value for key, value in required_config.items())


def policy_fixture_result(
    fixture: Mapping[str, Any],
    *,
    source_path: Path,
    effective_config: Mapping[str, Any],
    probe_source: ProbeSource | None,
) -> dict[str, Any]:
    fixture_id = str(fixture["id"])
    scenario_overlay = fixture.get("config_overlay") if isinstance(fixture.get("config_overlay"), Mapping) else {}
    scenario_config = dict(effective_config) | dict(scenario_overlay)
    if not is_applicable(fixture, scenario_config):
        return {"id": fixture_id, "status": "not_applicable", "findings": []}
    findings: list[dict[str, str]] = []
    if not source_path.is_file():
        findings.append({"severity": "error", "code": "source_missing", "message": "Owned fixture source is missing."})
    else:
        actual_hash = sha256_file(source_path)
        if actual_hash.casefold() != str(fixture["sha256"]).casefold():
            findings.append({"severity": "error", "code": "source_hash_mismatch", "message": "Owned fixture SHA-256 differs from catalog."})
        if probe_source is not None:
            try:
                actual_facts = probe_source(source_path)
                mismatches = facts_match(fixture.get("source_facts", {}), actual_facts)
                if mismatches:
                    findings.append({"severity": "error", "code": "source_topology_mismatch", "message": f"Source facts differ: {', '.join(mismatches)}."})
            except RuntimeError as exc:
                findings.append({"severity": "error", "code": "source_probe_failed", "message": str(exc)})
    return {"id": fixture_id, "status": "passed" if not findings else "failed", "findings": findings}


def verify_policy_proof_pack(
    *,
    fixture_root: Path,
    catalog_path: Path = DEFAULT_CATALOG,
    allowed_root: Path = DEFAULT_FIXTURE_ROOT,
    effective_config: Mapping[str, Any] | None = None,
    probe_source: ProbeSource | None = None,
) -> dict[str, Any]:
    root = assert_allowed_policy_root(fixture_root, allowed_root=allowed_root)
    fixtures = load_catalog(catalog_path)
    mapping = load_source_mapping(root, allowed_root=allowed_root)
    config = dict(effective_config or {})
    rows: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    for fixture in fixtures:
        source_path = mapping.get(str(fixture["source_key"]))
        if source_path is None:
            result = {"id": fixture["id"], "status": "failed", "findings": [{"severity": "error", "code": "source_mapping_missing", "message": "Fixture source_key is not mapped."}]}
        else:
            result = policy_fixture_result(fixture, source_path=source_path, effective_config=config, probe_source=probe_source)
        rows.append(result)
        findings.extend(result["findings"])
    return {"ok": not findings, "fixture_root": str(root), "fixtures": rows, "findings": findings}


def prepare_run_root(run_root: Path, *, fixture_root: Path, rebuild: bool) -> Path:
    allowed_runs = fixture_root / "runs"
    if not is_under(run_root, allowed_runs) or run_root.resolve(strict=False) == allowed_runs.resolve(strict=False):
        raise ValueError(f"Policy proof run root must be a child of {allowed_runs}")
    sentinel = run_root / RUN_SENTINEL
    if run_root.exists() and any(run_root.iterdir()):
        if not rebuild:
            raise FileExistsError(f"Policy proof run root already exists: {run_root}")
        if not sentinel.exists():
            raise ValueError(f"Refusing to rebuild run root without {RUN_SENTINEL}: {run_root}")
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    return run_root


def materialize_policy_proof_pack(
    *,
    fixture_root: Path,
    catalog_path: Path = DEFAULT_CATALOG,
    run_id: str,
    allowed_root: Path = DEFAULT_FIXTURE_ROOT,
    rebuild: bool = False,
    probe_source: ProbeSource | None = None,
) -> dict[str, Any]:
    root = assert_allowed_policy_root(fixture_root, allowed_root=allowed_root)
    verification = verify_policy_proof_pack(
        fixture_root=root,
        catalog_path=catalog_path,
        allowed_root=allowed_root,
        probe_source=probe_source,
    )
    if not verification["ok"]:
        return {"ok": False, "action": "materialize", "verification": verification}
    fixtures = load_catalog(catalog_path)
    mapping = load_source_mapping(root, allowed_root=allowed_root)
    run_root = prepare_run_root(root / "runs" / run_id, fixture_root=root, rebuild=rebuild)
    source_root = run_root / "source" / "Movies"
    source_root.mkdir(parents=True)
    records: list[dict[str, str]] = []
    for fixture in fixtures:
        source = mapping[str(fixture["source_key"])]
        suffix = source.suffix or ".mkv"
        destination = source_root / f"{fixture['id']}{suffix}"
        shutil.copy2(source, destination)
        source_facts = fixture["source_facts"]
        video_codec = "h264" if source_facts.get("stream_counts", {}).get("video", 0) else ""
        audio_codec = "aac" if source_facts.get("stream_counts", {}).get("audio", 0) else ""
        records.append(
            {
                "schema_version": tdarr_matrix_audit.AUDIT_SCHEMA.replace("audit", "materialized_library"),
                "view": "movies",
                "case_id": str(fixture["id"]),
                "diagnostic_bucket": "policy-proof",
                "generated_path": str(destination.relative_to(run_root)).replace("\\", "/"),
                # Subsequent backend-worker materialization must copy from this isolated
                # source copy, never from the owned fixture path.
                "source_path": str(destination),
                "original_name": source.name,
                "source_url": "owned-sanitized",
                "source_page": "policy-proof-catalog",
                "medium": "video" if video_codec else "audio",
                "container": suffix.lstrip(".") or "mkv",
                "resolution": str(source_facts.get("resolution") or "unknown"),
                "video_codec": video_codec,
                "audio_codec": audio_codec,
                "duration": "owned",
                "advertised_size_mb": "",
                "actual_size_bytes": str(destination.stat().st_size),
                "sha256": str(fixture["sha256"]),
                "link_mode": "copy",
            }
        )
    manifest_root = run_root / "manifests"
    manifest_root.mkdir()
    with (manifest_root / "materialized_library.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tdarr_matrix_audit.MANIFEST_FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)
    shutil.copy2(catalog_path, manifest_root / "policy_proof_catalog.json")
    (run_root / RUN_SENTINEL).write_text(
        json.dumps({"schema_version": CATALOG_SCHEMA, "created_at_utc": utc_now(), "fixture_count": len(records)}, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"ok": True, "action": "materialize", "run_root": str(run_root), "fixture_count": len(records)}


def write_policy_reports(run_root: Path, *, fixtures: list[dict[str, Any]], findings: list[dict[str, str]]) -> Path:
    manifest_root = run_root / "manifests"
    payload = {
        "schema_version": CATALOG_SCHEMA,
        "generated_at_utc": utc_now(),
        "run_root": str(run_root),
        "fixtures": fixtures,
        "findings": findings,
    }
    json_path = manifest_root / REPORT_NAME
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_lines = ["# Policy Proof Report", "", f"Run root: `{run_root}`", "", "| Fixture | Status | Findings |", "| --- | --- | --- |"]
    markdown_lines.extend(
        f"| {row['id']} | {row['status']} | {', '.join(item['code'] for item in row['findings']) or 'none'} |"
        for row in fixtures
    )
    (manifest_root / REPORT_MARKDOWN_NAME).write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    with (manifest_root / REPORT_CSV_NAME).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("fixture_id", "status", "severity", "code", "message"))
        writer.writeheader()
        for row in fixtures:
            if row["findings"]:
                for finding in row["findings"]:
                    writer.writerow({"fixture_id": row["id"], "status": row["status"], **finding})
            else:
                writer.writerow({"fixture_id": row["id"], "status": row["status"], "severity": "", "code": "", "message": ""})
    return json_path


def ps_literal(value: object) -> str:
    if isinstance(value, bool):
        return "$true" if value else "$false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return materializer.ps_array(value)
    if isinstance(value, str):
        return materializer.ps_quote(value)
    raise ValueError(f"Unsupported policy-proof config overlay value: {value!r}")


def apply_config_overlay(config_path: Path, overlay: Mapping[str, Any]) -> None:
    if not overlay:
        return
    text = config_path.read_text(encoding="utf-8")
    for key, value in overlay.items():
        text = materializer.replace_psd1_key(text, str(key), ps_literal(value))
    config_path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8", newline="\n")


def output_facts_for_worker(worker_result: Mapping[str, Any], *, ffprobe: str) -> dict[str, Any]:
    output_path = Path(str(worker_result.get("OutputPath") or ""))
    if not output_path.is_file():
        return {}
    return probe_source_ffprobe(output_path, ffprobe=ffprobe)


def pending_sidecar_kinds(pending_root: Path) -> list[str]:
    kinds: set[str] = set()
    for manifest_path in pending_root.glob("*.manifest.json") if pending_root.exists() else ():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        for sidecar in payload.get("sidecar_files", []) if isinstance(payload, dict) else []:
            if isinstance(sidecar, Mapping) and sidecar.get("kind"):
                kinds.add(str(sidecar["kind"]))
    return sorted(kinds)


def drain_isolated_pending_publish(
    *,
    execution_root: Path,
    config_path: Path,
    powershell: str,
    entrypoint: Path,
    timeout_seconds: int,
) -> tuple[bool, list[str]]:
    pending_root = execution_root / "scratch" / "State" / "PendingServerPush"
    sidecar_kinds = pending_sidecar_kinds(pending_root)
    command = [*tdarr_matrix_audit.build_powershell_file_command(powershell, entrypoint), "-ConfigPath", str(config_path), "-DrainPendingPushes"]
    audit_dir = tdarr_matrix_audit.default_audit_dir(execution_root)
    outcome = tdarr_matrix_audit.run_subprocess_capture(
        command,
        cwd=REPO_ROOT,
        timeout_seconds=timeout_seconds,
        stdout_path=audit_dir / "pending_drain_stdout.log",
        stderr_path=audit_dir / "pending_drain_stderr.log",
    )
    manifests_remaining = list(pending_root.glob("*.manifest.json")) if pending_root.exists() else []
    return outcome.returncode == 0 and not outcome.timed_out and not manifests_remaining, sidecar_kinds


def execute_backend_fixture(
    fixture: Mapping[str, Any],
    *,
    materialized_root: Path,
    powershell: str,
    entrypoint: Path,
    template_path: Path,
    ffprobe: str,
    sample_timeout_seconds: int,
) -> Mapping[str, Any]:
    """Execute one fixture through the backend-owned SingleFile worker in an isolated child root."""
    source_rows = tdarr_matrix_audit.load_manifest_rows(
        materialized_root / "manifests" / "materialized_library.csv",
        library_root=materialized_root,
    )
    fixture_id = str(fixture["id"])
    rows = [row for row in source_rows if row.case_id == fixture_id]
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one materialized row for policy fixture {fixture_id}")
    execution_root = materialized_root / "executions" / fixture_id
    tdarr_matrix_audit.materialize_run_subset(
        rows=rows,
        run_root=execution_root,
        template_path=template_path,
        rebuild=True,
    )
    config_path = execution_root / "config" / tdarr_matrix_audit.CONFIG_NAME
    overlay = fixture.get("config_overlay") if isinstance(fixture.get("config_overlay"), Mapping) else {}
    apply_config_overlay(config_path, overlay)
    prepared_config, _queue_snapshot, prepare_findings = tdarr_matrix_audit.prepare_pipeline_evidence(
        library_root=execution_root,
        config_path=config_path,
        powershell=powershell,
        entrypoint=entrypoint,
        timeout_seconds=tdarr_matrix_audit.DEFAULT_PREPARE_TIMEOUT_SECONDS,
    )
    run_rows = tdarr_matrix_audit.load_manifest_rows(
        execution_root / "manifests" / "materialized_library.csv",
        library_root=execution_root,
    )
    resilience = fixture.get("resilience") if isinstance(fixture.get("resilience"), Mapping) else {}
    interrupted = False
    if resilience.get("interrupt_and_rerun") is True:
        interrupt_result_path = tdarr_matrix_audit.default_audit_dir(execution_root) / "files" / tdarr_matrix_audit.safe_slug(f"{fixture_id}-movies-interrupted") / "worker_result.json"
        interrupt_result_path.parent.mkdir(parents=True, exist_ok=True)
        interrupt_command = tdarr_matrix_audit.build_single_file_command(
            powershell,
            entrypoint,
            prepared_config,
            execution_root / run_rows[0].generated_path,
            interrupt_result_path,
            run_id=f"policy-proof-{fixture_id}-interrupt",
            claim_id=tdarr_matrix_audit.safe_slug(f"{fixture_id}-interrupt"),
        )
        interrupted_outcome = tdarr_matrix_audit.run_subprocess_capture(
            interrupt_command,
            cwd=REPO_ROOT,
            timeout_seconds=max(1, int(resilience.get("interrupt_after_seconds") or 1)),
            stdout_path=interrupt_result_path.parent / "stdout.log",
            stderr_path=interrupt_result_path.parent / "stderr.log",
        )
        interrupted = interrupted_outcome.timed_out
        if not interrupted:
            raise RuntimeError("Controlled interruption fixture completed before its interruption timeout.")
    worker_findings = tdarr_matrix_audit.run_sample_processing(
        rows=run_rows,
        library_root=execution_root,
        config_path=prepared_config,
        powershell=powershell,
        entrypoint=entrypoint,
        run_id=f"policy-proof-{fixture_id}",
        timeout_seconds=sample_timeout_seconds,
    )
    result_path = tdarr_matrix_audit.default_audit_dir(execution_root) / "files" / tdarr_matrix_audit.safe_slug(f"{fixture_id}-movies") / "worker_result.json"
    worker_result = tdarr_matrix_audit.load_worker_result(result_path) or {}
    if interrupted:
        worker_result = dict(worker_result)
        worker_result["PolicyProofInterrupted"] = True
    publish_expectations = fixture.get("expectations", {}).get("publish", {}) if isinstance(fixture.get("expectations"), Mapping) else {}
    if publish_expectations.get("terminal_state") == "drained":
        drained, sidecar_kinds = drain_isolated_pending_publish(
            execution_root=execution_root,
            config_path=prepared_config,
            powershell=powershell,
            entrypoint=entrypoint,
            timeout_seconds=sample_timeout_seconds,
        )
        worker_result = dict(worker_result)
        worker_result["PublishState"] = "drained" if drained else str(worker_result.get("PublishState") or "parked")
        worker_result["SidecarKinds"] = sidecar_kinds
    source_findings = tdarr_matrix_audit.audit_source_hashes(run_rows)
    fatal_findings = [finding for finding in [*prepare_findings, *worker_findings, *source_findings] if finding.severity in {"critical", "error"}]
    if fatal_findings:
        raise RuntimeError("; ".join(f"{finding.code}: {finding.message}" for finding in fatal_findings))
    return {"output_facts": output_facts_for_worker(worker_result, ffprobe=ffprobe), "worker_result": worker_result}


def run_policy_proof_pack(
    *,
    fixture_root: Path,
    catalog_path: Path = DEFAULT_CATALOG,
    run_id: str,
    allowed_root: Path = DEFAULT_FIXTURE_ROOT,
    effective_config: Mapping[str, Any] | None = None,
    process_fixture: Callable[[Mapping[str, Any], Path], Mapping[str, Any]],
    rebuild: bool = False,
    probe_source: ProbeSource | None = None,
) -> dict[str, Any]:
    """Materialize sources, collect backend-owned evidence, and enforce catalog assertions."""
    materialized = materialize_policy_proof_pack(
        fixture_root=fixture_root,
        catalog_path=catalog_path,
        run_id=run_id,
        allowed_root=allowed_root,
        rebuild=rebuild,
        probe_source=probe_source,
    )
    if not materialized.get("ok"):
        verification = materialized.get("verification", {})
        return {"ok": False, "fixtures": [], "findings": verification.get("findings", []), "materialized": materialized}
    run_root = Path(str(materialized["run_root"]))
    config = dict(effective_config or {})
    rows: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    for fixture in load_catalog(catalog_path):
        fixture_id = str(fixture["id"])
        scenario_overlay = fixture.get("config_overlay") if isinstance(fixture.get("config_overlay"), Mapping) else {}
        if not is_applicable(fixture, config | dict(scenario_overlay)):
            rows.append({"id": fixture_id, "status": "not_applicable", "findings": []})
            continue
        try:
            evidence = process_fixture(fixture, run_root)
            output_facts = evidence.get("output_facts") if isinstance(evidence.get("output_facts"), Mapping) else {}
            worker_result = evidence.get("worker_result") if isinstance(evidence.get("worker_result"), Mapping) else {}
            fixture_findings = assert_output_expectations(fixture, output_facts=output_facts, worker_result=worker_result)
        except (OSError, RuntimeError, ValueError) as exc:
            fixture_findings = [{"severity": "error", "code": "fixture_execution_failed", "message": str(exc)}]
        rows.append({"id": fixture_id, "status": "passed" if not fixture_findings else "failed", "findings": fixture_findings})
        findings.extend(fixture_findings)
    report_path = write_policy_reports(run_root, fixtures=rows, findings=findings)
    return {"ok": not findings, "run_root": str(run_root), "report_path": str(report_path), "fixtures": rows, "findings": findings}


def exit_code_for_policy_result(result: Mapping[str, Any], *, strict: bool) -> int:
    if not strict:
        return 0
    findings = result.get("findings") if isinstance(result.get("findings"), list) else []
    return 1 if any(str(item.get("severity") or "").casefold() in {"critical", "error"} for item in findings if isinstance(item, Mapping)) else 0


def command_verify(args: argparse.Namespace) -> int:
    root = Path(args.fixture_root)
    try:
        result = verify_policy_proof_pack(
            fixture_root=root,
            catalog_path=Path(args.catalog),
            allowed_root=DEFAULT_FIXTURE_ROOT,
            probe_source=lambda path: probe_source_ffprobe(path, ffprobe=args.ffprobe),
        )
    except (OSError, RuntimeError, ValueError) as exc:
        result = {"ok": False, "fixture_root": str(root), "fixtures": [], "findings": [{"severity": "error", "code": "policy_proof_preflight_failed", "message": str(exc)}]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code_for_policy_result(result, strict=not args.report_only)


def command_materialize(args: argparse.Namespace) -> int:
    root = Path(args.fixture_root)
    try:
        result = materialize_policy_proof_pack(
            fixture_root=root,
            catalog_path=Path(args.catalog),
            run_id=args.run_id,
            allowed_root=DEFAULT_FIXTURE_ROOT,
            rebuild=bool(args.rebuild),
            probe_source=lambda path: probe_source_ffprobe(path, ffprobe=args.ffprobe),
        )
    except (OSError, RuntimeError, ValueError) as exc:
        result = {"ok": False, "action": "materialize", "error": str(exc)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


def command_run(args: argparse.Namespace) -> int:
    root = Path(args.fixture_root)
    try:
        result = run_policy_proof_pack(
            fixture_root=root,
            catalog_path=Path(args.catalog),
            run_id=args.run_id,
            allowed_root=DEFAULT_FIXTURE_ROOT,
            rebuild=bool(args.rebuild),
            probe_source=lambda path: probe_source_ffprobe(path, ffprobe=args.ffprobe),
            process_fixture=lambda fixture, run_root: execute_backend_fixture(
                fixture,
                materialized_root=run_root,
                powershell=args.powershell,
                entrypoint=Path(args.entrypoint),
                template_path=Path(args.template),
                ffprobe=args.ffprobe,
                sample_timeout_seconds=args.sample_timeout_seconds,
            ),
        )
    except (OSError, RuntimeError, ValueError) as exc:
        result = {"ok": False, "fixtures": [], "findings": [{"severity": "error", "code": "policy_proof_run_failed", "message": str(exc)}]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code_for_policy_result(result, strict=not args.report_only)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify and materialize isolated owned-media policy proof fixtures.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("verify", "materialize", "run"):
        child = subparsers.add_parser(command)
        child.add_argument("--fixture-root", default=str(DEFAULT_FIXTURE_ROOT))
        child.add_argument("--catalog", default=str(DEFAULT_CATALOG))
        child.add_argument("--ffprobe", default=str(DEFAULT_FFPROBE))
        child.add_argument("--report-only", action="store_true")
        if command in {"materialize", "run"}:
            child.add_argument("--run-id", required=True)
            child.add_argument("--rebuild", action="store_true")
        if command == "run":
            child.add_argument("--powershell", default=tdarr_matrix_audit.resolve_default_powershell())
            child.add_argument("--entrypoint", default=str(tdarr_matrix_audit.DEFAULT_PIPELINE_ENTRYPOINT))
            child.add_argument("--template", default=str(tdarr_matrix_audit.DEFAULT_TEMPLATE))
            child.add_argument("--sample-timeout-seconds", type=int, default=tdarr_matrix_audit.DEFAULT_SAMPLE_TIMEOUT_SECONDS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "verify":
        return command_verify(args)
    if args.command == "materialize":
        return command_materialize(args)
    if args.command == "run":
        return command_run(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
