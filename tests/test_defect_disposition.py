import sys
import unittest
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODEL_DIR))

from defect_disposition import DispositionInputs, decide, posterior_recoverable  # noqa: E402
from sweep_defect_disposition import render_svg, sweep  # noqa: E402


class DefectDispositionTest(unittest.TestCase):
    def setUp(self):
        self.inputs = DispositionInputs(0.45, 0.8, 0.9, 0.75, 0.18, 1.0, 0.10)

    def test_positive_response_raises_recoverable_probability(self):
        self.assertGreater(posterior_recoverable(self.inputs, True), 0.45)
        self.assertLess(posterior_recoverable(self.inputs, False), 0.45)

    def test_bayes_result_matches_hand_calculation(self):
        expected = (0.45 * 0.8) / (0.45 * 0.8 + 0.55 * 0.1)
        self.assertAlmostEqual(posterior_recoverable(self.inputs, True), expected)

    def test_synthetic_baseline_changes_action_with_signal(self):
        self.assertEqual(decide(self.inputs, True)["recommended_action"], "rework")
        self.assertEqual(decide(self.inputs, False)["recommended_action"], "scrap")

    def test_low_confirmation_cost_can_make_hold_optimal(self):
        ambiguous = DispositionInputs(0.5, 0.55, 0.55, 1.0, 0.35, 1.0, 0.01)
        self.assertEqual(decide(ambiguous, True)["recommended_action"], "hold_for_confirmation")

    def test_invalid_probability_is_rejected(self):
        invalid = DispositionInputs(1.1, 0.8, 0.9, 0.75, 0.18, 1.0, 0.08)
        with self.assertRaisesRegex(ValueError, "recoverable_prevalence"):
            posterior_recoverable(invalid, True)

    def test_sweep_is_complete_and_exposes_changed_condition(self):
        rows = sweep(self.inputs)
        self.assertEqual(len(rows), 76)
        actions = {(row["confirmation_cost"], row["response"], row["recommended_action"]) for row in rows}
        self.assertIn((0.08, "negative", "hold_for_confirmation"), actions)
        self.assertIn((0.10, "negative", "scrap"), actions)
        self.assertIn((0.10, "positive", "rework"), actions)
        svg = render_svg(rows)
        self.assertIn("Synthetic defect-disposition action boundaries", svg)
        self.assertIn("illustrative inputs only", svg)


if __name__ == "__main__":
    unittest.main()
