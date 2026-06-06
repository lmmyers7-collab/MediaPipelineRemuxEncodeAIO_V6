from __future__ import annotations

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from mediapipeline.contracts.api_commands import validate_api_command_payload
from mediapipeline.contracts.subtitles import validate_subtitle_qa_result
from mediapipeline.core.api.commands import COMMAND_ROUTE_METHODS
from mediapipeline.core.subtitles.qa import (
    build_completed_subtitle_qa,
    build_queue_subtitle_qa,
    subtitle_qa_item_from_payloads,
    subtitle_qa_summary_from_payloads,
)
from mediapipeline.desktop.api.contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT
from mediapipeline.desktop.api.contract_read import LOCAL_API_READ_ROUTE_CONTRACT
from mediapipeline.desktop.api.routes_read import GET_ROUTE_HANDLERS


class SubtitleQaFeatureTests(unittest.TestCase):
    def test_queue_qa_flags_forced_subtitles_as_review_only_evidence(self) -> None:
        qa = build_queue_subtitle_qa(
            {
                "row_key": "queue-1",
                "track_metadata_available": True,
                "subtitle_track_count": 2,
                "subtitle_languages": ["eng"],
                "has_forced_subtitles": True,
            }
        )

        self.assertEqual(qa["schema_version"], "subtitle_qa_result.v1")
        self.assertEqual(validate_subtitle_qa_result(qa)["schema_version"], "subtitle_qa_result.v1")
        self.assertEqual(qa["posture"], "review")
        self.assertEqual(qa["inventory"]["status"], "present")
        self.assertEqual(qa["srt_validity"]["status"], "not_checked")
        self.assertEqual(qa["sync_review"]["status"], "heuristic_only")
        self.assertIn("read-only", qa["guardrail"].lower())

    def test_completed_qa_passes_when_generated_srt_has_non_empty_cue_evidence(self) -> None:
        row = {
            "row_key": "completed-1",
            "source_path": "C:/Media/Input.mkv",
            "output_path": "C:/Media/Output.mkv",
            "output_exists": True,
            "subtitle_decision_count": 1,
            "subtitle_decision_preview": ["s:0 eng ass -> srt"],
        }
        qa = build_completed_subtitle_qa(
            row,
            subtitle_decisions=[
                {
                    "subtitle_ordinal": 0,
                    "language": "eng",
                    "source_codec": "ass",
                    "action": "srt",
                    "cue_count": 1420,
                    "output_path": "C:/Media/Output.eng.srt",
                    "tool": "ffmpeg",
                }
            ],
        )

        self.assertEqual(qa["posture"], "pass")
        self.assertEqual(qa["srt_validity"]["status"], "pass")
        self.assertEqual(qa["srt_validity"]["cue_count"], 1420)
        self.assertEqual(qa["conversion_evidence"]["status"], "pass")
        self.assertIn("ass", qa["inventory"]["source_codecs"])

    def test_completed_qa_reviews_image_subtitles_without_ocr_or_conversion_evidence(self) -> None:
        qa = build_completed_subtitle_qa(
            {
                "row_key": "completed-2",
                "source_path": "C:/Media/Input.mkv",
                "output_path": "C:/Media/Output.mkv",
                "output_exists": True,
                "subtitle_decision_count": 1,
            },
            subtitle_decisions=[
                {
                    "subtitle_ordinal": 0,
                    "language": "eng",
                    "source_codec": "pgs",
                    "action": "srt",
                }
            ],
        )

        self.assertEqual(qa["posture"], "review")
        self.assertEqual(qa["conversion_evidence"]["status"], "review")
        self.assertTrue(any("OCR/conversion evidence" in reason for reason in qa["reasons"]))

    def test_completed_qa_blocks_explicit_image_subtitle_ocr_failure(self) -> None:
        qa = build_completed_subtitle_qa(
            {
                "row_key": "completed-3",
                "source_path": "C:/Media/Input.mkv",
                "output_path": "C:/Media/Output.mkv",
                "output_exists": True,
                "subtitle_decision_count": 1,
            },
            subtitle_decisions=[
                {
                    "subtitle_ordinal": 0,
                    "language": "eng",
                    "source_codec": "pgs",
                    "action": "srt",
                    "failure_reason": "OCR tool path missing for PGS subtitle conversion.",
                }
            ],
        )

        self.assertEqual(qa["posture"], "blocked")
        self.assertEqual(qa["conversion_evidence"]["status"], "blocked")
        self.assertTrue(any("OCR tool path missing" in reason for reason in qa["reasons"]))

    def test_completed_qa_does_not_block_image_subtitle_with_cue_evidence(self) -> None:
        qa = build_completed_subtitle_qa(
            {
                "row_key": "completed-4",
                "source_path": "C:/Media/Input.mkv",
                "output_path": "C:/Media/Output.mkv",
                "output_exists": True,
                "subtitle_decision_count": 1,
            },
            subtitle_decisions=[
                {
                    "subtitle_ordinal": 0,
                    "language": "eng",
                    "source_codec": "pgs",
                    "action": "srt",
                    "cue_count": 980,
                    "output_path": "C:/Media/Output.eng.srt",
                }
            ],
        )

        self.assertEqual(qa["posture"], "pass")
        self.assertEqual(qa["conversion_evidence"]["status"], "pass")

    def test_summary_and_item_lookup_use_loaded_rows_only(self) -> None:
        queue_row = {
            "row_key": "queue-1",
            "source_path": "C:/Media/Input.mkv",
            "track_metadata_available": False,
        }
        queue_row["subtitle_qa"] = build_queue_subtitle_qa(queue_row)
        completed_row = {
            "row_key": "completed-1",
            "source_path": "C:/Media/Input.mkv",
            "output_path": "C:/Media/Output.mkv",
        }
        completed_row["subtitle_qa"] = build_completed_subtitle_qa(
            completed_row,
            subtitle_decisions=[
                {
                    "language": "eng",
                    "source_codec": "tx3g",
                    "action": "srt",
                    "cue_count": 120,
                    "tool": "ffmpeg",
                }
            ],
        )

        summary = subtitle_qa_summary_from_payloads({"rows": [queue_row]}, {"rows": [completed_row]})
        item = subtitle_qa_item_from_payloads({"rows": [queue_row]}, {"rows": [completed_row]}, "completed-1")

        self.assertEqual(summary["schema_version"], "subtitle_qa_summary.v1")
        self.assertEqual(summary["rows_loaded"], 2)
        self.assertEqual(summary["counts"]["unknown"], 1)
        self.assertEqual(item["status"], "matched")
        self.assertEqual(item["row_key"], "completed-1")
        self.assertEqual(item["scope"], "completed")

    def test_local_api_routes_and_contracts_include_subtitle_qa(self) -> None:
        self.assertEqual(GET_ROUTE_HANDLERS["/api/subtitle-qa/summary"].method_name, "_subtitle_qa_summary_payload")
        self.assertTrue(GET_ROUTE_HANDLERS["/api/subtitle-qa/item"].needs_query)
        self.assertEqual(COMMAND_ROUTE_METHODS["/api/subtitle-qa/preview"], "_subtitle_qa_preview_payload")
        payload = validate_api_command_payload("/api/subtitle-qa/preview", {"id": "completed-1", "limit": 50})
        self.assertEqual(payload["id"], "completed-1")
        self.assertEqual(payload["limit"], 50)

        read_paths = {row["path"] for row in LOCAL_API_READ_ROUTE_CONTRACT}
        command_paths = {row["path"] for row in LOCAL_API_COMMAND_ROUTE_CONTRACT}
        self.assertIn("/api/subtitle-qa/summary", read_paths)
        self.assertIn("/api/subtitle-qa/item", read_paths)
        self.assertIn("/api/subtitle-qa/preview", command_paths)


if __name__ == "__main__":
    unittest.main()
