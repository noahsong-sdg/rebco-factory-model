from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODEL_DIR))

from model import ModelInputError, poisson_piece_retention, run_factory  # noqa: E402


class FactoryModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        scenario = MODEL_DIR / "scenarios" / "illustrative_baseline.json"
        cls.baseline = json.loads(scenario.read_text(encoding="utf-8"))

    def test_rebco_growth_is_baseline_bottleneck(self) -> None:
        result = run_factory(self.baseline)
        self.assertEqual(result["bottleneck_step"], "rebco_growth")
        expected = 75 * 0.8 * 0.85 * 8000
        self.assertAlmostEqual(result["gross_master_m_per_year"], expected)

    def test_speeding_non_bottleneck_does_not_change_output(self) -> None:
        faster = copy.deepcopy(self.baseline)
        faster["steps"][0]["nominal_web_speed_m_per_hour"] *= 2
        baseline_result = run_factory(self.baseline)
        faster_result = run_factory(faster)
        self.assertEqual(
            faster_result["gross_master_m_per_year"],
            baseline_result["gross_master_m_per_year"],
        )

    def test_independent_retention_is_product_of_steps(self) -> None:
        result = run_factory(self.baseline)
        expected = 1.0
        for step in self.baseline["steps"]:
            expected *= step["independent_retention"]
        self.assertAlmostEqual(result["independent_process_retention"], expected)

    def test_zero_defects_have_full_piece_retention(self) -> None:
        self.assertEqual(poisson_piece_retention(0, 10, 500), 1.0)

    def test_stricter_piece_length_reduces_retention(self) -> None:
        short = poisson_piece_retention(2.0, 1.0, 50)
        long = poisson_piece_retention(2.0, 1.0, 500)
        self.assertLess(long, short)

    def test_common_defect_affects_all_lane_order_risk(self) -> None:
        result = run_factory(self.baseline)
        self.assertLessEqual(
            result["all_lanes_clean_order_probability"],
            result["single_lane_clean_order_probability"],
        )

    def test_higher_ic_reduces_cost_per_kam_but_not_cost_per_m(self) -> None:
        higher_ic = copy.deepcopy(self.baseline)
        for grade in higher_ic["grades"]:
            grade["ic_a_at_reference"] *= 2
        baseline_result = run_factory(self.baseline)
        higher_result = run_factory(higher_ic)
        self.assertAlmostEqual(
            higher_result["manufacturing_cost_per_qualified_m"],
            baseline_result["manufacturing_cost_per_qualified_m"],
        )
        self.assertAlmostEqual(
            higher_result["manufacturing_cost_per_kam"],
            baseline_result["manufacturing_cost_per_kam"] / 2,
        )

    def test_downgraded_saleable_output_is_not_counted_as_qualified(self) -> None:
        result = run_factory(self.baseline)
        self.assertAlmostEqual(result["qualified_grade_share"], 0.8)
        self.assertAlmostEqual(
            result["qualified_tape_m_per_year"],
            result["saleable_tape_m_per_year"] * 0.8,
        )
        expected_kam = result["saleable_tape_m_per_year"] * (0.3 * 0.5 + 0.5 * 0.35)
        self.assertAlmostEqual(result["qualified_kam_per_year"], expected_kam)

    def test_width_normalization_preserves_area_basis(self) -> None:
        result = run_factory(self.baseline)
        expected = result["gross_slit_tape_m_per_year"] * 4 / 12
        self.assertAlmostEqual(result["gross_12mm_equivalent_m_per_year"], expected)

    def test_slit_width_cannot_exceed_master_width(self) -> None:
        invalid = copy.deepcopy(self.baseline)
        invalid["factory"]["slit_tape_width_mm"] = 5
        with self.assertRaisesRegex(ModelInputError, "cannot exceed master_width"):
            run_factory(invalid)

    def test_at_least_one_grade_must_be_qualified(self) -> None:
        invalid = copy.deepcopy(self.baseline)
        for grade in invalid["grades"]:
            grade["counts_as_qualified_output"] = False
        with self.assertRaisesRegex(ModelInputError, "at least one grade"):
            run_factory(invalid)

    def test_grade_shares_must_sum_to_one(self) -> None:
        invalid = copy.deepcopy(self.baseline)
        invalid["grades"][0]["share"] = 0.4
        with self.assertRaisesRegex(ModelInputError, "shares must sum to 1"):
            run_factory(invalid)

    def test_negative_defect_rate_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.baseline)
        invalid["defects"]["lane_defects_per_lane_km"] = -1
        with self.assertRaises(ModelInputError):
            run_factory(invalid)

    def test_reference_condition_is_required(self) -> None:
        invalid = copy.deepcopy(self.baseline)
        invalid["reference_condition"] = ""
        with self.assertRaisesRegex(ModelInputError, "reference_condition"):
            run_factory(invalid)

    def test_evidence_notice_is_required(self) -> None:
        invalid = copy.deepcopy(self.baseline)
        invalid["evidence_notice"] = ""
        with self.assertRaisesRegex(ModelInputError, "evidence_notice"):
            run_factory(invalid)


if __name__ == "__main__":
    unittest.main()
