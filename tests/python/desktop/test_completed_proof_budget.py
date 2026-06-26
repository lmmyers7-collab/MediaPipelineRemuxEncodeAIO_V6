"""Packet 1 (backend-load-performance): completed-job live-proof budgeting.

These tests pin the contract that broad completed reads no longer perform a
synchronous Path.exists()/stat() sweep for every manifest row, while keeping the
evidence explicit (live vs deferred) and leaving full live proof available on
demand.
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import Mock, patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.completed.manifest import (
    OUTPUT_PROOF_DEFERRED,
    OUTPUT_PROOF_LIVE,
    read_completed_manifest_records,
)
from mediapipeline.core.completed.policy import (
    completed_record_to_row,
    completed_row_operator_status_state,
)
from mediapipeline.desktop.api.read_payloads_inventory import (
    LocalApiInventoryReadPayloadMixin,
)
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import CompletedJobRecord
from tests.python.desktop.application_facade_test_support import DummyWorkflowFacadeService, _resolved


def _logger() -> logging.Logger:
    logger = logging.getLogger("test_completed_proof_budget")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


def _write_manifest(directory: Path, count: int) -> Path:
    manifest = directory / "completed_jobs.jsonl"
    manifest.write_text(
        "\n".join(
            json.dumps({"output_file": f"movie-{index}.mkv", "encoded_at": "2026-05-07T21:00:00-04:00"})
            for index in range(count)
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _record(proof: str) -> CompletedJobRecord:
    return CompletedJobRecord(
        sidecar_path=Path(r"C:\Media\Movie.pipeline.json"),
        payload={
            "output_path": r"C:\Media\Movie.mkv",
            "output_size": 2048,
            "source_size": 4096,
            "encoded_at": "2026-05-07T21:00:00-04:00",
            "_diagnostics_output_proof": proof,
        },
    )


class CompletedManifestProofBudgetTests(unittest.TestCase):
    def test_summary_mode_skips_all_live_proof_and_marks_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            manifest = _write_manifest(Path(td), 5)
            with patch("mediapipeline.core.completed.manifest.annotate_completed_output_health") as spy:
                rows = read_completed_manifest_records(
                    manifest, limit=None, logger=_logger(), proof_mode="summary"
                )
        self.assertEqual(spy.call_count, 0)
        self.assertEqual([r.payload["_diagnostics_output_proof"] for r in rows], [OUTPUT_PROOF_DEFERRED] * 5)
        # No live annotation means the existence sentinel is never written.
        self.assertTrue(all("_diagnostics_output_exists" not in r.payload for r in rows))

    def test_bounded_mode_proves_only_budgeted_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            manifest = _write_manifest(Path(td), 5)
            with patch("mediapipeline.core.completed.manifest.annotate_completed_output_health") as spy:
                rows = read_completed_manifest_records(
                    manifest,
                    limit=None,
                    logger=_logger(),
                    proof_mode="bounded",
                    bounded_proof_limit=2,
                )
        self.assertEqual(spy.call_count, 2)
        self.assertEqual(
            [r.payload["_diagnostics_output_proof"] for r in rows],
            [OUTPUT_PROOF_LIVE, OUTPUT_PROOF_LIVE, OUTPUT_PROOF_DEFERRED, OUTPUT_PROOF_DEFERRED, OUTPUT_PROOF_DEFERRED],
        )

    def test_live_mode_is_default_and_proves_every_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            manifest = _write_manifest(Path(td), 3)
            with patch("mediapipeline.core.completed.manifest.annotate_completed_output_health") as spy:
                rows = read_completed_manifest_records(manifest, limit=None, logger=_logger())
        self.assertEqual(spy.call_count, 3)
        self.assertEqual([r.payload["_diagnostics_output_proof"] for r in rows], [OUTPUT_PROOF_LIVE] * 3)


class CompletedRowProofDtoTests(unittest.TestCase):
    def test_deferred_row_reports_not_checked_without_touching_filesystem(self) -> None:
        record = _record(OUTPUT_PROOF_DEFERRED)
        with patch.object(Path, "exists", autospec=True, return_value=True) as mock_exists, patch.object(
            Path, "stat", autospec=True
        ) as mock_stat:
            mock_stat.return_value.st_mtime = 1.0
            mock_stat.return_value.st_size = 2048
            row = completed_record_to_row(record)
        self.assertEqual(mock_exists.call_count, 0)
        self.assertEqual(mock_stat.call_count, 0)
        self.assertIsNone(row["output_exists"])
        self.assertEqual(row["output_proof"], OUTPUT_PROOF_DEFERRED)
        self.assertEqual(row["consistency_status"], "Unverified")
        self.assertEqual(row["validation_status_state"], "validation-needed")
        self.assertNotIn("missing_output", row.get("consistency_issues") or [])
        # Output size still surfaces from the manifest payload, not from disk.
        self.assertEqual(row["output_size_bytes"], 2048)

    def test_deferred_row_operator_status_is_unverified_not_match(self) -> None:
        # Review finding LOW-1: a proof-deferred row has unproven existence, so
        # its operator status must not read as the all-clear "match".
        deferred = completed_record_to_row(_record(OUTPUT_PROOF_DEFERRED))
        self.assertIsNone(deferred["output_exists"])
        self.assertEqual(completed_row_operator_status_state(deferred), "unverified")
        with patch.object(Path, "exists", autospec=True, return_value=True), patch.object(
            Path, "stat", autospec=True
        ) as mock_stat:
            mock_stat.return_value.st_mtime = 1.0
            mock_stat.return_value.st_size = 2048
            live = completed_record_to_row(_record(OUTPUT_PROOF_LIVE))
        self.assertIs(live["output_exists"], True)
        self.assertEqual(completed_row_operator_status_state(live), "match")

    def test_live_row_performs_real_proof_and_marks_live(self) -> None:
        record = _record(OUTPUT_PROOF_LIVE)
        with patch.object(Path, "exists", autospec=True, return_value=True) as mock_exists, patch.object(
            Path, "stat", autospec=True
        ) as mock_stat:
            mock_stat.return_value.st_mtime = 1.0
            mock_stat.return_value.st_size = 2048
            row = completed_record_to_row(record)
        self.assertGreater(mock_exists.call_count, 0)
        self.assertIs(row["output_exists"], True)
        self.assertEqual(row["output_proof"], OUTPUT_PROOF_LIVE)


class CompletedProofCacheKeyTests(unittest.TestCase):
    def test_summary_cache_is_not_served_to_a_live_request(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            output = root / "Outsource" / "Movies" / "Movie (2024).mkv"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"x" * 2048)
            sidecar = output.with_suffix(".pipeline.json")
            sidecar.write_text("{}", encoding="utf-8")
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "source_path": str(root / "Source" / "Movie.mkv"),
                        "output_path": str(output),
                        "route": "encode",
                        "encoded_at": "2026-05-07T21:00:00-04:00",
                        "source_size": 4096,
                        "output_size": 2048,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            summary = facade.get_completed_preview(resolved, proof_mode="summary").to_mapping()
            # Same manifest path + mtime; only the proof mode differs. The proof
            # mode must be part of the cache key or the live read would be served
            # the cached summary evidence.
            live = facade.get_completed_preview(resolved, proof_mode="live").to_mapping()

        self.assertIsNone(summary["rows"][0]["output_exists"])
        self.assertEqual(summary["rows"][0]["output_proof"], OUTPUT_PROOF_DEFERRED)
        self.assertIs(live["rows"][0]["output_exists"], True)
        self.assertEqual(live["rows"][0]["output_proof"], OUTPUT_PROOF_LIVE)


class _CompletedRouteHost(LocalApiInventoryReadPayloadMixin):
    def __init__(self, facade: object, resolved: object) -> None:
        self.facade = facade
        self._resolved_value = resolved

    def _resolved(self) -> object:
        return self._resolved_value


class CompletedRouteProofDefaultTests(unittest.TestCase):
    def _host(self) -> tuple[_CompletedRouteHost, dict[str, object]]:
        captured: dict[str, object] = {}
        facade = Mock()

        def _get_completed_preview(resolved: object, **kwargs: object) -> Mock:
            captured.update(kwargs)
            result = Mock()
            result.to_mapping.return_value = {"rows": []}
            return result

        facade.get_completed_preview.side_effect = _get_completed_preview
        # Force the pending-proof cross-check into its defensive branch so the
        # route still returns; we only care about the completed proof default.
        facade.get_pending_publish_preview.side_effect = RuntimeError("no pending in test")
        return _CompletedRouteHost(facade, object()), captured

    def test_broad_completed_route_defaults_to_bounded_proof(self) -> None:
        host, captured = self._host()
        host._completed_payload({})
        self.assertEqual(captured["proof_mode"], "bounded")

    def test_completed_route_honors_explicit_live_proof(self) -> None:
        host, captured = self._host()
        host._completed_payload({"proof": ["live"]})
        self.assertEqual(captured["proof_mode"], "live")


if __name__ == "__main__":
    unittest.main()
