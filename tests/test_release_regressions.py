import unittest, random, copy, json, math
from pathlib import Path
from defect_simulation import retained_fraction, _poisson_count
from defect_disposition import DispositionInputs
from ramp_economics import run_ramp
from model import run_factory, ModelInputError
ROOT = Path(__file__).resolve().parents[1]
class ReleaseRegressionTest(unittest.TestCase):
    def test_defect_free_short_roll_is_not_shippable(self):
        self.assertEqual(retained_fraction([], 50, 0, 100), 0)
        self.assertEqual(retained_fraction([], 100, 0, 100), 1)
    def test_large_poisson_mean_does_not_saturate(self):
        rng = random.Random(42)
        mean = sum(_poisson_count(1000, rng) for _ in range(100))/100
        self.assertTrue(970 < mean < 1030, mean)
    def test_nonfinite_cost_is_rejected(self):
        for bad in (math.nan, math.inf):
            with self.assertRaises(ValueError):
                DispositionInputs(.5,.8,.8,.9,bad,1,1).validate()
    def test_fractional_or_boolean_year_is_rejected(self):
        cfg = json.loads((ROOT/'scenarios/ramp-cash-diagnostic.json').read_text())
        for bad in (1.9, True):
            cfg['years'][0]['year'] = bad
            with self.assertRaises(ModelInputError): run_ramp(cfg)
    def test_zero_yield_underflow_has_clear_error(self):
        cfg = json.loads((ROOT/'scenarios/illustrative_baseline.json').read_text())
        cfg['defects']['minimum_shippable_piece_m'] = 1e9
        with self.assertRaisesRegex(ModelInputError, 'zero output'): run_factory(cfg)
