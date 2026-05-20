from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application.facade_completed_policy import (
    COMPLETED_HISTORY_EMPTY_MESSAGE,
    COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE,
    bounded_completed_limit,
    completed_history_read_error_result,
    completed_history_service_unavailable_result,
    completed_preview_fields,
    completed_preview_from_records,
    completed_preview_rows,
    completed_record_key,
    completed_record_to_row,
    format_bytes_compact,
)
from mediapipeline_desktop_app.models import CompletedJobRecord


def _record(
    *,
    source: str = "C:/Source/Movie.mkv",
    output: str = "C:/Outsource/Movies/Movie (2024)/Movie (2024).mkv",
    sidecar: str = "C:/Outsource/Movies/Movie (2024)/Movie (2024).pipeline.json",
    route: str = "encode",
    output_size: int = 2048,
    output_exists: bool = True,
    size_policy: dict[str, object] | None = None,
) -> CompletedJobRecord:
    payload = {
        "source_path": source,
        "output_path": output,
        "route": route,
        "encoded_at": "2026-05-07T21:00:00-04:00",
        "elapsed_seconds": 65,
        "source_size": 4096,
        "output_size": output_size,
        "_diagnostics_output_exists": output_exists,
        "_diagnostics_output_health": "ok" if output_exists else "missing",
        "publish_state": "published",
        "publish_mode": "immediate",
        "encode_selected_encoder": "hevc_nvenc",
        "encode_selected_encoder_kind": "gpu",
        "encode_selected_gpu_device": "NVIDIA",
        "audio_decisions": [{"action": "copy"}],
        "subtitle_decisions": [{"action": "srt"}],
    }
    if size_policy is not None:
        payload["size_policy"] = size_policy
    return CompletedJobRecord(
        sidecar_path=Path(sidecar),
        payload=payload,
    )


class CompletedFacadePolicyTests(unittest.TestCase):
    def test_bounded_limit_matches_existing_completed_preview_bounds(self) -> None:
        self.assertEqual(bounded_completed_limit(None), 100)
        self.assertEqual(bounded_completed_limit("bad"), 100)
        self.assertEqual(bounded_completed_limit(0), 100)
        self.assertEqual(bounded_completed_limit(-3), 1)
        self.assertEqual(bounded_completed_limit(999), 500)
        self.assertEqual(bounded_completed_limit("25"), 25)

    def test_format_bytes_compact_uses_existing_units(self) -> None:
        self.assertEqual(format_bytes_compact(-1), "0 B")
        self.assertEqual(format_bytes_compact(0), "0 B")
        self.assertEqual(format_bytes_compact(1536), "1.5 KB")
        self.assertEqual(format_bytes_compact(2 * 1024**2), "2.0 MB")
        self.assertEqual(format_bytes_compact(3 * 1024**3), "3.00 GB")

    def test_completed_record_key_and_row_are_stable(self) -> None:
        record = _record()
        repeated = _record()
        changed_route = _record(route="remux")
        row = completed_record_to_row(record)

        self.assertEqual(completed_record_key(record), completed_record_key(repeated))
        self.assertNotEqual(completed_record_key(record), completed_record_key(changed_route))
        self.assertEqual(len(row["row_key"]), 24)
        self.assertEqual(row["route"], "encode")
        self.assertEqual(row["route_label"], "ENCODE")
        self.assertEqual(row["elapsed"], "1m 5s")
        self.assertEqual(row["publish"], "Published")
        self.assertEqual(row["output_file"], "Movie (2024).mkv")
        self.assertTrue(row["output_exists"])
        self.assertEqual(row["output_health"], "ok")
        self.assertEqual(row["source_size_bytes"], 4096)
        self.assertEqual(row["output_size_text"], "2.0 KB")
        self.assertFalse(row["size_policy_available"])
        self.assertEqual(row["size_policy_status"], "unavailable")
        self.assertEqual(row["encoder"], "hevc_nvenc")
        self.assertEqual(row["encoder_kind"], "gpu")
        self.assertEqual(row["gpu_device"], "NVIDIA")
        self.assertEqual(row["audio_decision_count"], 1)
        self.assertEqual(row["subtitle_decision_count"], 1)
        self.assertEqual(row["available_open_targets"], ["output_file", "output_folder", "sidecar", "source_folder"])

    def test_completed_row_counts_singleton_decision_objects(self) -> None:
        record = _record()
        record.payload["audio_decisions"] = {"action": "copy", "source_codec": "ac3", "language": "eng"}
        record.payload["subtitle_decisions"] = {
            "action": "convertass",
            "source_codec": "ass",
            "language": "eng",
        }

        row = completed_record_to_row(record)

        self.assertEqual(row["audio_decision_count"], 1)
        self.assertEqual(row["subtitle_decision_count"], 1)
        self.assertEqual(row["subtitle_decision_preview"], ["s:? eng ass -> convertass"])

    def test_preview_rows_filter_non_records_and_fields_count_routes(self) -> None:
        encode = _record(route="encode", output_size=2048, output_exists=True)
        cpu_fallback = _record(
            output="C:/Outsource/Movies/CPU (2024)/CPU (2024).mkv",
            sidecar="C:/Outsource/Movies/CPU (2024)/CPU (2024).pipeline.json",
            route="encode-cpu-fallback",
            output_size=1024,
            output_exists=False,
        )
        remux = _record(
            output="C:/Outsource/Movies/Remux (2024)/Remux (2024).mkv",
            sidecar="C:/Outsource/Movies/Remux (2024)/Remux (2024).pipeline.json",
            route="remux",
            output_size=512,
            output_exists=True,
        )

        rows = completed_preview_rows([encode, "not-a-record", cpu_fallback, remux])
        fields = completed_preview_fields(rows, source="completed_jobs.jsonl")

        self.assertEqual(len(rows), 3)
        self.assertEqual(fields["source"], "completed_jobs.jsonl")
        self.assertEqual(fields["count"], 3)
        self.assertEqual(fields["missing_output_count"], 1)
        self.assertEqual(fields["encode_count"], 2)
        self.assertEqual(fields["remux_count"], 1)
        self.assertEqual(fields["total_output_bytes"], 3584)
        self.assertEqual(fields["total_output_size_text"], "3.5 KB")
        self.assertEqual(fields["size_policy_available_count"], 0)
        self.assertEqual(fields["size_policy_exceeded_count"], 0)
        self.assertEqual(fields["size_policy_within_limit_count"], 0)
        self.assertEqual(
            fields["available_open_target_counts"],
            {"output_file": 2, "output_folder": 3, "sidecar": 3, "source_folder": 3},
        )
        self.assertEqual(fields["warnings"], [])

    def test_empty_preview_fields_keep_operator_warning(self) -> None:
        fields = completed_preview_fields([], source="completed_jobs.jsonl")

        self.assertEqual(fields["count"], 0)
        self.assertEqual(fields["total_output_size_text"], "0 B")
        self.assertEqual(fields["warnings"], ["No completed jobs are available from the local manifest."])

    def test_completed_preview_dto_helpers_preserve_warning_contracts(self) -> None:
        unavailable = completed_history_service_unavailable_result()
        read_error = completed_history_read_error_result(Path("C:/State/Completed/completed_jobs.jsonl"), RuntimeError("locked"))

        self.assertEqual(unavailable.warnings, [COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE])
        self.assertEqual(read_error.source, str(Path("C:/State/Completed/completed_jobs.jsonl")))
        self.assertEqual(read_error.warnings, ["Completed history could not be read: locked"])

    def test_completed_preview_from_records_wraps_fields_in_dto(self) -> None:
        preview = completed_preview_from_records(
            [_record(route="remux"), "not-a-record"],
            source="completed_jobs.jsonl",
        )

        self.assertEqual(preview.source, "completed_jobs.jsonl")
        self.assertEqual(preview.count, 1)
        self.assertEqual(preview.remux_count, 1)
        self.assertEqual(preview.warnings, [])

        empty = completed_preview_from_records([], source="completed_jobs.jsonl")
        self.assertEqual(empty.warnings, [COMPLETED_HISTORY_EMPTY_MESSAGE])

    def test_size_policy_allows_compatibility_growth_above_legacy_five_percent(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            output = root / "Outsource" / "Movies" / "Compatibility (2024)" / "Compatibility (2024).mkv"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"x")
            sidecar = output.with_suffix(".pipeline.json")
            sidecar.write_text("{}", encoding="utf-8")
            record = _record(
                source=str(root / "Source" / "Compatibility.mkv"),
                output=str(output),
                sidecar=str(sidecar),
                output_size=4506,
                size_policy={
                    "mode": "advisory",
                    "routing_profile": "plex_direct_stream",
                    "route_reason_code": "codec_outside_policy",
                    "max_growth_percent": 15,
                    "limit_ratio": 1.15,
                    "source_size_bytes": 4096,
                    "output_size_bytes": 4506,
                    "ratio": 1.1,
                    "exceeded": False,
                    "enforced": False,
                    "message": "encoded output is 1.10x source; within 1.15x limit",
                },
            )

            preview = completed_preview_from_records([record], source="completed_jobs.jsonl").to_mapping()
        row = preview["rows"][0]

        self.assertTrue(row["size_growth_over_5"])
        self.assertTrue(row["size_policy_available"])
        self.assertEqual(row["size_policy_status"], "within_policy")
        self.assertEqual(row["size_policy_mode"], "advisory")
        self.assertEqual(row["size_policy_limit_label"], "+15% (1.15x)")
        self.assertFalse(row["size_policy_exceeded"])
        self.assertEqual(row["size_policy_delta_vs_limit_percent"], -4.99)
        self.assertEqual(row["operator_status"], "Size policy allowed")
        self.assertEqual(row["operator_severity"], "ok")
        self.assertEqual(row["operator_trust_state"], "consistent-looking")
        self.assertIn("size_policy_within_limit", row["review_flags"])
        self.assertNotIn("size_growth_over_5", row["review_flags"])
        self.assertIn(
            "Size policy: advisory; profile=plex_direct_stream; limit=+15% (1.15x); status=within_policy; encoded output is 1.10x source; within 1.15x limit",
            row["route_evidence_lines"],
        )
        self.assertEqual(preview["size_policy_available_count"], 1)
        self.assertEqual(preview["size_policy_within_limit_count"], 1)
        self.assertEqual(preview["size_policy_exceeded_count"], 0)
        self.assertEqual(preview["size_policy_mode_counts"], {"advisory": 1})
        self.assertEqual(preview["operator_severity_counts"], {"ok": 1})

    def test_size_policy_exceeded_rows_are_explicit_operator_review(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            output = root / "Outsource" / "Movies" / "Big (2024)" / "Big (2024).mkv"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"x")
            sidecar = output.with_suffix(".pipeline.json")
            sidecar.write_text("{}", encoding="utf-8")
            record = _record(
                source=str(root / "Source" / "Big.mkv"),
                output=str(output),
                sidecar=str(sidecar),
                output_size=8192,
                size_policy={
                    "mode": "advisory",
                    "routing_profile": "plex_direct_stream",
                    "route_reason_code": "size_over_threshold",
                    "max_growth_percent": 5,
                    "limit_ratio": 1.05,
                    "source_size_bytes": 4096,
                    "output_size_bytes": 8192,
                    "ratio": 2.0,
                    "exceeded": True,
                    "enforced": False,
                    "message": "encoded output is 2.00x source; exceeds 1.05x limit (5% growth policy)",
                },
            )

            preview = completed_preview_from_records([record], source="completed_jobs.jsonl").to_mapping()
        row = preview["rows"][0]

        self.assertTrue(row["size_policy_available"])
        self.assertEqual(row["size_policy_status"], "review")
        self.assertTrue(row["size_policy_exceeded"])
        self.assertFalse(row["size_policy_enforced"])
        self.assertEqual(row["operator_status"], "Review size policy")
        self.assertEqual(row["operator_severity"], "warning")
        self.assertIn("size_policy_exceeded", row["review_flags"])
        self.assertIn("recorded backend size policy threshold", row["primary_concern"])
        self.assertEqual(preview["size_policy_exceeded_count"], 1)
        self.assertEqual(preview["size_policy_blocked_count"], 0)
        self.assertEqual(preview["size_policy_status_counts"], {"review": 1})


if __name__ == "__main__":
    unittest.main()
