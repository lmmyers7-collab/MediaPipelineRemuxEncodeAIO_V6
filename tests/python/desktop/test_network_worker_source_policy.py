from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))


DESKTOP_ROOT = find_repo_root(Path(__file__)) / "src" / "mediapipeline" / "desktop"
NETWORK_ROOT = DESKTOP_ROOT / "network"


def network_source(*module_names: str) -> str:
    return "\n".join((NETWORK_ROOT / f"{name}.py").read_text(encoding="utf-8") for name in module_names)


class NetworkWorkerSourcePolicyTests(unittest.TestCase):
    def test_worker_uses_shared_network_diagnostic_preview(self) -> None:
        source = network_source("worker")

        self.assertIn("from .diagnostics import diagnostic_preview as _worker_diagnostic_preview", source)
        self.assertNotIn("def _worker_diagnostic_preview", source)

    def test_claim_record_build_failure_emits_cluster_event(self) -> None:
        source = network_source("worker_loops")

        self.assertIn("Failed to build QueueRecord for claimed job", source)
        self.assertIn('event="claim_record_invalid"', source)
        self.assertIn("Worker could not build QueueRecord for claimed job", source)
        self.assertIn("job_id=claim.job_id", source)
        self.assertIn("source_path=claim.source_path", source)
        self.assertIn("reason_preview = _worker_diagnostic_preview(exc)", source)
        self.assertIn("self._release_unstartable_claim(claim, reason_preview)", source)

    def test_heartbeat_progress_snapshot_failures_are_logged(self) -> None:
        source = network_source("worker_loops")

        self.assertIn("Heartbeat progress snapshot read failed", source)
        self.assertIn("_log.warning", source)
        self.assertIn("sending 0%% progress", source)

    def test_cluster_log_post_failures_warn_with_event_context(self) -> None:
        source = network_source("worker")

        self.assertIn("cluster log POST failed for event %s", source)
        self.assertNotIn("cluster log POST failed: %s", source)

    def test_claim_request_failures_warn_once_per_error_text(self) -> None:
        source = network_source("worker_loops")

        self.assertIn("Worker claim request failed; poll loop will retry", source)
        self.assertIn("_last_claim_failure_text", source)
        self.assertIn("Claim request still failing", source)

    def test_heartbeat_post_failures_warn_once_per_error_text(self) -> None:
        source = network_source("worker_loops")

        self.assertIn("Worker heartbeat POST failed for job %s; heartbeat loop will retry", source)
        self.assertIn("_last_heartbeat_failure_text", source)
        self.assertIn("Heartbeat POST still failing", source)

    def test_worker_poll_interval_uses_policy_helper(self) -> None:
        source = network_source("worker")

        self.assertIn("resolve_worker_poll_interval", source)
        self.assertIn("KEY_WORKER_POLL_INTERVAL_SECS", source)
        self.assertIn("resolve_worker_poll_interval(config.get(KEY_WORKER_POLL_INTERVAL_SECS))", source)
        self.assertNotIn("KEY_WORKER_POLL_INTERVAL_SECS, 30", source)
        self.assertNotIn('config.get("WorkerPollIntervalSecs", 30)', source)
        self.assertNotIn('max(5, int(config.get("WorkerPollIntervalSecs", 30)))', source)

    def test_accepted_done_report_cleanup_does_not_save_pending_report(self) -> None:
        source = network_source("worker_state", "worker_claims")

        self.assertIn("_clear_worker_state_after_accepted_report", source)
        self.assertIn("return False", source)
        self.assertIn("return True", source)
        self.assertIn("not saving a pending done report", source)
        self.assertIn('self._clear_worker_state_after_accepted_report(job.job_id, "done")', source)
        self.assertIn('self._clear_worker_state_after_accepted_report(job.job_id, "release")', source)
        self.assertIn('self._clear_worker_state_after_accepted_report(job.job_id, "internal release")', source)
        self.assertIn('"pending done recovery"', source)
        self.assertIn('"crash recovery done"', source)

    def test_crash_recovery_state_anomalies_are_logged(self) -> None:
        source = network_source("worker_state")

        self.assertIn("worker_state.json missing job_id", source)
        self.assertIn("Ignoring malformed pending done report", source)
        self.assertIn("falling back to crash-failed recovery", source)

    def test_terminal_report_logs_distinguish_acceptance_from_pending_retry(self) -> None:
        source = network_source("worker_claims")

        self.assertIn("report accepted by coordinator", source)
        self.assertIn("completion report pending retry after coordinator POST failure", source)
        self.assertIn("release report pending retry after coordinator POST failure", source)
        self.assertIn("internal release report accepted by coordinator", source)
        self.assertIn("internal release report pending retry after coordinator POST failure", source)
        self.assertNotIn("Job %s reported %s.", source)
        self.assertNotIn("Job %s released.", source)


if __name__ == "__main__":
    unittest.main()
