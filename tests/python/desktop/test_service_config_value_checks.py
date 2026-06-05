from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.config.value_checks import (
    add_unique_warning,
    require_non_empty,
    validate_float,
    validate_int,
    validate_optional_float,
    validate_optional_int,
)


class ServiceConfigValueCheckTests(unittest.TestCase):
    def test_require_non_empty_reports_blank_values(self) -> None:
        errors: list[str] = []

        require_non_empty({"SourceMovies": " "}, errors, "SourceMovies", "SourceMovies")

        self.assertEqual(errors, ["SourceMovies is required."])

    def test_validate_int_reports_type_and_bounds(self) -> None:
        errors: list[str] = []

        validate_int({"VideoQuality": "22"}, errors, "VideoQuality", "VideoQuality", minimum=1, maximum=51)
        validate_int({"VideoQuality": 99}, errors, "VideoQuality", "VideoQuality", minimum=1, maximum=51)

        self.assertEqual(errors, ["VideoQuality must be an integer.", "VideoQuality must be <= 51."])

    def test_validate_float_reports_type_and_bounds(self) -> None:
        errors: list[str] = []

        validate_float({"Multiplier": "bad"}, errors, "Multiplier", "Multiplier", minimum=0.1, maximum=2.0)
        validate_float({"Multiplier": 0.01}, errors, "Multiplier", "Multiplier", minimum=0.1, maximum=2.0)

        self.assertEqual(errors, ["Multiplier must be numeric.", "Multiplier must be >= 0.1."])

    def test_optional_validators_skip_blank_values(self) -> None:
        errors: list[str] = []

        validate_optional_int({"Threads": ""}, errors, "Threads", "Threads", minimum=0)
        validate_optional_float({"Multiplier": None}, errors, "Multiplier", "Multiplier", minimum=0.1)

        self.assertEqual(errors, [])

    def test_add_unique_warning_deduplicates_messages(self) -> None:
        warnings: list[str] = []

        add_unique_warning(warnings, "Scratch is inside source.")
        add_unique_warning(warnings, "Scratch is inside source.")

        self.assertEqual(warnings, ["Scratch is inside source."])


if __name__ == "__main__":
    unittest.main()
