from __future__ import annotations

import unittest

from app.contracts.verification import (
    evaluate_output_size_check,
    output_size_check_action_from_settings,
    verification_result_from_size_check,
)


class VerificationContractTests(unittest.TestCase):
    def test_legacy_size_guard_modes_map_to_explicit_output_size_actions(self) -> None:
        self.assertEqual(output_size_check_action_from_settings("off"), "disabled")
        self.assertEqual(output_size_check_action_from_settings("advisory"), "warn_only")
        self.assertEqual(output_size_check_action_from_settings("strict"), "fail_job")
        self.assertEqual(output_size_check_action_from_settings("advisory", "block_publish"), "block_publish")

    def test_warn_only_size_check_records_advisory_without_failure_or_publish_block(self) -> None:
        check = evaluate_output_size_check(
            action="warn_only",
            source_size_bytes=100,
            actual_output_size_bytes=130,
            growth_tolerance_percent=10,
        )
        result = verification_result_from_size_check(check)

        self.assertEqual(check.status, "warning")
        self.assertEqual(check.on_fail, "record_advisory_warning")
        self.assertEqual(len(result.advisory_warnings), 1)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.publish_blockers, [])

    def test_block_publish_size_check_records_publish_blocker_not_failure(self) -> None:
        check = evaluate_output_size_check(
            action="block_publish",
            source_size_bytes=100,
            actual_output_size_bytes=130,
            growth_tolerance_percent=10,
        )
        result = verification_result_from_size_check(check)

        self.assertEqual(check.status, "blocked")
        self.assertEqual(check.on_fail, "park_pending_publish")
        self.assertEqual(result.advisory_warnings, [])
        self.assertEqual(result.failures, [])
        self.assertEqual(len(result.publish_blockers), 1)

    def test_fail_job_size_check_records_failure_not_publish_blocker(self) -> None:
        check = evaluate_output_size_check(
            action="fail_job",
            source_size_bytes=100,
            actual_output_size_bytes=130,
            growth_tolerance_percent=10,
        )
        result = verification_result_from_size_check(check)

        self.assertEqual(check.status, "failed")
        self.assertEqual(check.on_fail, "fail_job")
        self.assertEqual(result.advisory_warnings, [])
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.publish_blockers, [])


if __name__ == "__main__":
    unittest.main()
