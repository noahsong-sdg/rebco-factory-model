import copy
import json
import sys
import unittest
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODEL_DIR))

from defect_simulation import retained_fraction, simulate_piece_yield  # noqa: E402
from compare_defect_models import compare_defect_models  # noqa: E402
from model import ModelInputError  # noqa: E402


class DefectSimulationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = json.loads(
            (MODEL_DIR / "scenarios" / "illustrative_clustered_defects.json").read_text(encoding="utf-8")
        )

    def test_zero_defects_retain_whole_length(self) -> None:
        self.assertEqual(retained_fraction([], 1000, 1, 100), 1.0)

    def test_minimum_piece_rule_discards_short_clean_segments(self) -> None:
        defects = [100, 250]
        permissive = retained_fraction(defects, 400, 1, 25)
        strict = retained_fraction(defects, 400, 1, 200)
        self.assertLess(strict, permissive)

    def test_seed_makes_clustered_simulation_reproducible(self) -> None:
        first = simulate_piece_yield(self.baseline)
        second = simulate_piece_yield(self.baseline)
        self.assertEqual(first, second)

    def test_common_only_defects_make_lane_mean_equal_worst_lane(self) -> None:
        scenario = copy.deepcopy(self.baseline)
        scenario["lane_defects_per_lane_km"] = 0
        result = simulate_piece_yield(scenario)
        self.assertAlmostEqual(
            result["mean_lane_retained_fraction"],
            result["mean_worst_lane_retained_fraction"],
        )

    def test_lane_defects_create_worst_lane_penalty(self) -> None:
        result = simulate_piece_yield(self.baseline)
        self.assertLessEqual(
            result["mean_worst_lane_retained_fraction"],
            result["mean_lane_retained_fraction"],
        )

    def test_missing_seed_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.baseline)
        del invalid["seed"]
        with self.assertRaisesRegex(ModelInputError, "seed"):
            simulate_piece_yield(invalid)

    def test_comparison_holds_marginal_rate_fixed_and_is_reproducible(self) -> None:
        config = json.loads(
            (MODEL_DIR / "scenarios" / "piece-yield-diagnostic.json").read_text(encoding="utf-8")
        )
        first = compare_defect_models(config)
        second = compare_defect_models(config)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first["expected_marginal_defects_per_lane_km"], 1.2)
        self.assertEqual(len(first["rows"]), 12)
        frozen_means = {
            (row["minimum_shippable_piece_m"], row["variant"]): round(
                row["mean_lane_retained_fraction"], 4
            )
            for row in first["rows"]
        }
        self.assertEqual(
            frozen_means,
            {
                (25, "independent-poisson"): 0.9976,
                (25, "clustered-10m"): 0.9943,
                (25, "clustered-100m"): 0.9949,
                (100, "independent-poisson"): 0.9817,
                (100, "clustered-10m"): 0.9909,
                (100, "clustered-100m"): 0.9674,
                (300, "independent-poisson"): 0.8737,
                (300, "clustered-10m"): 0.9668,
                (300, "clustered-100m"): 0.9228,
                (500, "independent-poisson"): 0.7161,
                (500, "clustered-10m"): 0.9216,
                (500, "clustered-100m"): 0.8810,
            },
        )

    def test_comparison_rejects_rate_changing_variant(self) -> None:
        config = json.loads(
            (MODEL_DIR / "scenarios" / "piece-yield-diagnostic.json").read_text(encoding="utf-8")
        )
        config["variants"][0]["lane_defects_per_lane_km"] = 2.0
        with self.assertRaisesRegex(ModelInputError, "preserve"):
            compare_defect_models(config)


if __name__ == "__main__":
    unittest.main()
