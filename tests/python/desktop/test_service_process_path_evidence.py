from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.processes.path_evidence import (
    LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS,
    PATH_HEALTH_UNC_RETRY_TIMEOUT_SECONDS,
    configured_path_health,
    is_unc_path,
    path_evidence,
    path_health_warning_lines,
)


class ProcessPathEvidenceTests(unittest.TestCase):
    def test_unc_paths_do_not_probe_exists(self) -> None:
        def fail_exists(_path: Path) -> bool:
            raise AssertionError("UNC preflight evidence must not call Path.exists")

        with patch.object(Path, "exists", fail_exists):
            evidence, details = path_evidence(Path(r"\\LAYNE-SERVER\Share\file.csv"))

        self.assertTrue(is_unc_path(r"\\LAYNE-SERVER\Share"))
        self.assertTrue(is_unc_path(r"\\?\UNC\LAYNE-SERVER\Share"))
        self.assertFalse(is_unc_path(r"\\?\C:\Local"))
        self.assertEqual(evidence, "network path not checked")
        self.assertIn("exists=not checked", details)

    def test_local_paths_still_report_presence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            present = root / "file.csv"
            present.write_text("x\n", encoding="utf-8")

            present_evidence, _ = path_evidence(present)
            missing_evidence, _ = path_evidence(root / "missing.csv")

        self.assertEqual(present_evidence, "exists")
        self.assertEqual(missing_evidence, "missing on disk")

    def test_configured_path_health_reports_blocked_unc_roots_read_only(self) -> None:
        calls: list[str] = []

        def probe_runner(path_text: str, timeout_seconds: float) -> dict[str, object]:
            calls.append(path_text)
            self.assertEqual(timeout_seconds, 1.5)
            if path_text.startswith(r"\\LAYNE-SERVER"):
                return {
                    "path": path_text,
                    "server": "LAYNE-SERVER",
                    "share": "Video",
                    "dns_status": "blocked",
                    "tcp_445_status": "blocked",
                    "exists": False,
                    "path_kind": "missing",
                    "can_list": False,
                    "elapsed_ms": 12,
                }
            return {
                "path": path_text,
                "dns_status": "not_applicable",
                "tcp_445_status": "not_applicable",
                "exists": True,
                "path_kind": "directory",
                "can_list": True,
                "elapsed_ms": 3,
            }

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            resolved = SimpleNamespace(
                source_movies=None,
                source_tv=root / "TV",
                local_base=root / "Scratch",
                config_data={
                    "SourceMovies": r"\\LAYNE-SERVER\Video\Movies",
                    "SourceTV": str(root / "TV"),
                    "Outsource": r"\\LAYNE-SERVER\Video\Outsource",
                    "LocalBase": str(root / "Scratch"),
                    "LibraryProfiles": [
                        {
                            "id": "movies",
                            "name": "Movies",
                            "source_path": r"\\LAYNE-SERVER\Video\Movies",
                            "output_path": r"\\LAYNE-SERVER\Video\Outsource",
                        }
                    ],
                },
            )

            payload = configured_path_health(
                resolved,
                timeout_seconds=1.5,
                cache_ttl_seconds=0,
                probe_runner=probe_runner,
            )

        self.assertEqual(payload["schema_version"], "desktop_configured_path_health.v1")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["operator_status"], "blocked")
        self.assertEqual(payload["blocked_count"], 2)
        self.assertEqual(payload["ready_count"], 2)
        self.assertEqual(len(calls), 4)
        rows = {row["key"]: row for row in payload["rows"]}
        self.assertEqual(rows["source_movies"]["status"], "blocked")
        self.assertEqual(rows["source_movies"]["server"], "LAYNE-SERVER")
        self.assertEqual(rows["source_movies"]["write_probe"]["status"], "not_checked")
        self.assertGreaterEqual(len(rows["source_movies"]["references"]), 2)
        self.assertEqual(rows["source_tv"]["status"], "ready")
        warnings = path_health_warning_lines(payload)
        self.assertTrue(any("Log back into Windows/server share" in line for line in warnings))
        self.assertIn("no recursive scan", "\n".join(payload["summary_lines"]))

    def test_configured_path_health_reports_storage_reserves_for_scratch_and_output(self) -> None:
        gib = 1024**3

        def probe_runner(path_text: str, timeout_seconds: float) -> dict[str, object]:
            _ = timeout_seconds
            free_gb = 40 if path_text.endswith("Scratch") else 25
            return {
                "path": path_text,
                "dns_status": "not_applicable",
                "tcp_445_status": "not_applicable",
                "exists": True,
                "path_kind": "directory",
                "can_list": True,
                "free_bytes": free_gb * gib,
                "total_bytes": 100 * gib,
                "used_bytes": (100 - free_gb) * gib,
                "elapsed_ms": 2,
            }

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            resolved = SimpleNamespace(
                source_movies=None,
                source_tv=root / "TV",
                local_base=root / "Scratch",
                config_data={
                    "SourceTV": str(root / "TV"),
                    "Outsource": str(root / "Outsource"),
                    "LocalBase": str(root / "Scratch"),
                    "MinFreeSpaceGB": 50,
                    "OutsourceMinFreeSpaceGB": 20,
                },
            )

            payload = configured_path_health(
                resolved,
                timeout_seconds=1,
                cache_ttl_seconds=0,
                probe_runner=probe_runner,
            )

        rows = {row["key"]: row for row in payload["rows"]}
        scratch = rows["local_base"]
        output = rows["outsource"]
        source = rows["source_tv"]
        self.assertEqual(scratch["status"], "ready")
        self.assertEqual(scratch["storage_status"], "low")
        self.assertEqual(scratch["reserve_key"], "MinFreeSpaceGB")
        self.assertEqual(scratch["reserve_gb"], 50.0)
        self.assertEqual(scratch["free_space_gb"], 40.0)
        self.assertFalse(scratch["meets_space_reserve"])
        self.assertEqual(output["storage_status"], "ready")
        self.assertEqual(output["reserve_key"], "OutsourceMinFreeSpaceGB")
        self.assertEqual(output["reserve_gb"], 20.0)
        self.assertEqual(output["free_space_gb"], 25.0)
        self.assertTrue(output["meets_space_reserve"])
        self.assertEqual(source["storage_status"], "not_checked")
        self.assertEqual(scratch["health_code"], "free_space_low")

    def test_configured_path_health_retries_timed_out_unc_once(self) -> None:
        calls: list[float] = []

        def probe_runner(path_text: str, timeout_seconds: float) -> dict[str, object]:
            calls.append(timeout_seconds)
            if len(calls) == 1:
                return {
                    "path": path_text,
                    "server": "SLOW-SERVER",
                    "share": "Video",
                    "timed_out": True,
                    "path_error": "Path health probe timed out.",
                    "elapsed_ms": int(timeout_seconds * 1000),
                }
            return {
                "path": path_text,
                "server": "SLOW-SERVER",
                "share": "Video",
                "dns_status": "ready",
                "tcp_445_status": "ready",
                "exists": True,
                "path_kind": "directory",
                "can_list": True,
                "elapsed_ms": 25,
                "phase_timings_ms": {"path": 10, "list": 15},
            }

        resolved = SimpleNamespace(
            source_movies=None,
            source_tv=None,
            local_base=None,
            config_data={"SourceMovies": r"\\SLOW-SERVER\Video\Movies"},
        )
        with patch("mediapipeline.core.processes.path_evidence.time.sleep"):
            payload = configured_path_health(
                resolved,
                timeout_seconds=LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS,
                cache_ttl_seconds=0,
                probe_runner=probe_runner,
            )

        row = payload["rows"][0]
        self.assertEqual(payload["operator_status"], "ready")
        self.assertEqual(row["status"], "ready")
        self.assertEqual(row["health_code"], "path_ready")
        self.assertEqual(calls, [LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS, PATH_HEALTH_UNC_RETRY_TIMEOUT_SECONDS])
        self.assertEqual(len(row["probe_attempts"]), 2)
        self.assertTrue(row["probe_attempts"][0]["timed_out"])
        self.assertEqual(row["phase_timings_ms"], {"path": 10, "list": 15})

    def test_configured_path_health_repeated_unc_timeout_remains_blocked(self) -> None:
        calls: list[float] = []

        def probe_runner(path_text: str, timeout_seconds: float) -> dict[str, object]:
            calls.append(timeout_seconds)
            return {
                "path": path_text,
                "server": "TIMEOUT-SERVER",
                "share": "Video",
                "timed_out": True,
                "path_error": f"Path health probe exceeded {timeout_seconds:g} seconds.",
                "elapsed_ms": int(timeout_seconds * 1000),
            }

        resolved = SimpleNamespace(
            source_movies=None,
            source_tv=None,
            local_base=None,
            config_data={"Outsource": r"\\TIMEOUT-SERVER\Video\Out"},
        )
        with patch("mediapipeline.core.processes.path_evidence.time.sleep"):
            payload = configured_path_health(
                resolved,
                timeout_seconds=LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS,
                cache_ttl_seconds=0,
                probe_runner=probe_runner,
            )

        row = payload["rows"][0]
        self.assertEqual(payload["operator_status"], "blocked")
        self.assertEqual(row["status"], "blocked")
        self.assertEqual(row["health_code"], "path_timeout")
        self.assertEqual(row["storage_status"], "blocked")
        self.assertIsNone(row["free_space_gb"])
        self.assertEqual(len(row["probe_attempts"]), 2)
        self.assertEqual(calls, [LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS, PATH_HEALTH_UNC_RETRY_TIMEOUT_SECONDS])

    def test_configured_path_health_does_not_retry_missing_unc(self) -> None:
        calls: list[float] = []

        def probe_runner(path_text: str, timeout_seconds: float) -> dict[str, object]:
            calls.append(timeout_seconds)
            return {
                "path": path_text,
                "server": "MISSING-SERVER",
                "share": "Video",
                "dns_status": "ready",
                "tcp_445_status": "ready",
                "exists": False,
                "path_kind": "missing",
                "can_list": False,
                "elapsed_ms": 4,
            }

        resolved = SimpleNamespace(
            source_movies=None,
            source_tv=None,
            local_base=None,
            config_data={"SourceMovies": r"\\MISSING-SERVER\Video\Movies"},
        )
        payload = configured_path_health(
            resolved,
            timeout_seconds=LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS,
            cache_ttl_seconds=0,
            probe_runner=probe_runner,
        )

        row = payload["rows"][0]
        self.assertEqual(calls, [LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS])
        self.assertEqual(row["status"], "blocked")
        self.assertEqual(row["health_code"], "path_missing_or_unreachable")
        self.assertEqual(len(row["probe_attempts"]), 1)

    def test_configured_path_health_surfaces_share_root_capacity_fallback(self) -> None:
        gib = 1024**3

        def probe_runner(path_text: str, timeout_seconds: float) -> dict[str, object]:
            _ = timeout_seconds
            return {
                "path": path_text,
                "server": "LAYNE-SERVER",
                "share": "Users",
                "dns_status": "ready",
                "tcp_445_status": "ready",
                "exists": True,
                "path_kind": "directory",
                "can_list": True,
                "disk_error": "configured path capacity failed",
                "capacity_error": "configured path capacity failed",
                "capacity_source": "share_root_fallback",
                "capacity_path": r"\\LAYNE-SERVER\Users",
                "free_bytes": 125 * gib,
                "total_bytes": 200 * gib,
                "used_bytes": 75 * gib,
                "elapsed_ms": 18,
                "phase_timings_ms": {"list": 3, "disk_usage": 10, "disk_usage_share_root": 5},
            }

        resolved = SimpleNamespace(
            source_movies=None,
            source_tv=None,
            local_base=None,
            config_data={
                "Outsource": r"\\LAYNE-SERVER\Users\Layne\Videos\outsource\Movies",
                "OutsourceMinFreeSpaceGB": 50,
            },
        )
        payload = configured_path_health(
            resolved,
            timeout_seconds=LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS,
            cache_ttl_seconds=0,
            probe_runner=probe_runner,
        )

        row = payload["rows"][0]
        self.assertEqual(row["status"], "ready")
        self.assertEqual(row["storage_status"], "ready")
        self.assertEqual(row["health_code"], "ready_with_capacity")
        self.assertEqual(row["capacity_source"], "share_root_fallback")
        self.assertEqual(row["capacity_path"], r"\\LAYNE-SERVER\Users")
        self.assertEqual(row["free_space_gb"], 125.0)
        self.assertEqual(row["last_successful_capacity"]["capacity_source"], "share_root_fallback")

    def test_configured_path_health_last_successful_capacity_is_evidence_only(self) -> None:
        gib = 1024**3
        path = r"\\CACHE-SERVER\Video\Out"

        def successful_probe(path_text: str, timeout_seconds: float) -> dict[str, object]:
            _ = timeout_seconds
            return {
                "path": path_text,
                "server": "CACHE-SERVER",
                "share": "Video",
                "dns_status": "ready",
                "tcp_445_status": "ready",
                "exists": True,
                "path_kind": "directory",
                "can_list": True,
                "capacity_source": "configured_path",
                "capacity_path": path_text,
                "free_bytes": 120 * gib,
                "total_bytes": 200 * gib,
                "used_bytes": 80 * gib,
                "elapsed_ms": 5,
            }

        def timed_out_probe(path_text: str, timeout_seconds: float) -> dict[str, object]:
            _ = timeout_seconds
            return {
                "path": path_text,
                "server": "CACHE-SERVER",
                "share": "Video",
                "timed_out": True,
                "path_error": "Path health probe timed out.",
                "elapsed_ms": 2000,
            }

        resolved = SimpleNamespace(
            source_movies=None,
            source_tv=None,
            local_base=None,
            config_data={
                "Outsource": path,
                "OutsourceMinFreeSpaceGB": 50,
            },
        )
        ready_payload = configured_path_health(
            resolved,
            timeout_seconds=LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS,
            cache_ttl_seconds=0,
            probe_runner=successful_probe,
        )
        with patch("mediapipeline.core.processes.path_evidence.time.sleep"):
            blocked_payload = configured_path_health(
                resolved,
                timeout_seconds=LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS,
                cache_ttl_seconds=0,
                probe_runner=timed_out_probe,
            )

        ready_row = ready_payload["rows"][0]
        blocked_row = blocked_payload["rows"][0]
        self.assertEqual(ready_row["storage_status"], "ready")
        self.assertEqual(blocked_row["status"], "blocked")
        self.assertEqual(blocked_row["storage_status"], "blocked")
        self.assertIsNone(blocked_row["free_space_gb"])
        self.assertEqual(blocked_row["health_code"], "path_timeout")
        self.assertEqual(blocked_row["last_successful_capacity"]["free_space_gb"], 120.0)
        self.assertTrue(blocked_row["last_successful_capacity"]["evidence_only"])


if __name__ == "__main__":
    unittest.main()
