import copy
import json
import math
import sys
import unittest
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODEL_DIR))

from model import ModelInputError  # noqa: E402
from ramp_economics import run_ramp  # noqa: E402


class RampEconomicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = json.loads((MODEL_DIR / "scenarios" / "ramp-cash-diagnostic.json").read_text(encoding="utf-8"))

    def test_installed_nameplate_does_not_become_shipments_before_qualification(self):
        first = run_ramp(self.scenario)["years"][0]
        self.assertEqual(first["gross_kam"], 2500)
        self.assertEqual(first["qualified_kam"], 0)
        self.assertEqual(first["shipped_kam"], 0)
        self.assertTrue(math.isinf(first["manufacturing_cost_per_shipped_kam"]))

    def test_demand_caps_shipments_without_erasing_qualified_inventory(self):
        fourth = run_ramp(self.scenario)["years"][3]
        self.assertEqual(fourth["qualified_kam"], 7650)
        self.assertEqual(fourth["shipped_kam"], 7000)
        self.assertEqual(fourth["unshipped_qualified_kam"], 650)

    def test_revenue_growth_consumes_working_capital(self):
        years = run_ramp(self.scenario)["years"]
        self.assertEqual(years[0]["working_capital"], 0)
        self.assertGreater(years[1]["change_working_capital"], 0)
        self.assertAlmostEqual(years[1]["working_capital"], years[1]["revenue"] * 0.15)

    def test_npv_is_sum_of_discounted_cash_and_capex_is_counted_once(self):
        result = run_ramp(self.scenario)
        self.assertAlmostEqual(result["npv"], sum(row["discounted_cash_flow"] for row in result["years"]))
        self.assertEqual(result["total_capex"], 750000)

    def test_invalid_qualification_fraction_is_rejected(self):
        invalid = copy.deepcopy(self.scenario)
        invalid["years"][0]["qualified_fraction"] = 1.01
        with self.assertRaisesRegex(ModelInputError, "qualified_fraction"):
            run_ramp(invalid)

    def test_years_must_be_consecutive(self):
        invalid = copy.deepcopy(self.scenario)
        invalid["years"][1]["year"] = 3
        with self.assertRaisesRegex(ModelInputError, "consecutive"):
            run_ramp(invalid)

    def test_joint_delay_changes_both_ramps_and_worsens_cash_result(self):
        delayed_scenario = json.loads(
            (MODEL_DIR / "scenarios" / "ramp-cash-joint-delay-diagnostic.json").read_text(encoding="utf-8")
        )
        baseline = run_ramp(self.scenario)
        delayed = run_ramp(delayed_scenario)

        self.assertLess(delayed_scenario["years"][1]["utilization"], self.scenario["years"][1]["utilization"])
        self.assertLess(
            delayed_scenario["years"][1]["qualified_fraction"],
            self.scenario["years"][1]["qualified_fraction"],
        )
        self.assertLess(delayed["total_shipped_kam"], baseline["total_shipped_kam"])
        self.assertLess(delayed["npv"], baseline["npv"])
        self.assertIsNone(delayed["discounted_payback_year"])


if __name__ == "__main__":
    unittest.main()
