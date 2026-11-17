"""Independent hand-calculated accounting and entry-point regressions."""
import copy
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model import poisson_piece_retention, run_factory
from run_model import _render_markdown


class AccountingAndCliTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'scenarios/illustrative_baseline.json').read_text(encoding='utf-8'))

    def test_baseline_hand_accounting(self):
        r = run_factory(self.config)
        gross = 75 * .8 * .85 * 8000
        slit = gross * 3 * .97
        saleable = slit * (.99 * .98 * .94 * .99 * .96) * math.exp(-.0012 * 101) * 1.12
        cost = 6_000_000 + 22_000_000 + gross * 67 + slit * 3.5
        self.assertAlmostEqual(cost, 59_491_480)
        self.assertAlmostEqual(r['annual_manufacturing_cost'], cost)
        self.assertAlmostEqual(r['saleable_tape_m_per_year'], saleable)
        self.assertAlmostEqual(r['manufacturing_cost_per_kam'], cost / (saleable * (.3 * .5 + .5 * .35)))
        for grade in r['grades']:
            self.assertAlmostEqual(grade['allocated_manufacturing_cost_per_kam'], cost / saleable / (grade['ic_a_at_reference'] / 1000))
        self.assertIn(r['cost_allocation_basis'], _render_markdown(r))

    def test_poisson_formula_numeric_reference(self):
        # Exponential gap integral: rate=.01/m, excluded=2, minimum=100.
        self.assertAlmostEqual(poisson_piece_retention(10, 2, 100), 2 * math.exp(-1.02))

    def test_revenue_and_zero_revenue(self):
        for price in (100, 0):
            cfg = copy.deepcopy(self.config)
            for grade in cfg['grades']:
                grade['selling_price_per_m'] = price
            r = run_factory(cfg)
            self.assertAlmostEqual(r['annual_revenue'], price * r['saleable_tape_m_per_year'])
            if price:
                self.assertAlmostEqual(r['gross_margin_before_unmodeled_costs'], 1 - r['annual_manufacturing_cost'] / r['annual_revenue'])
            else:
                self.assertIsNone(r['gross_margin_before_unmodeled_costs'])
                self.assertIn('undefined (zero revenue)', _render_markdown(r))
            self.assertIn('Annual revenue:', _render_markdown(r))

    def test_all_cli_entry_points_from_another_directory(self):
        cases = [
            ('run_model.py', 'illustrative_baseline.json', []),
            ('run_defect_simulation.py', 'illustrative_clustered_defects.json', []),
            ('compare_defect_models.py', 'piece-yield-diagnostic.json', []),
            ('run_defect_disposition.py', 'defect-disposition-diagnostic.json', []),
            ('run_ramp_economics.py', 'ramp-cash-diagnostic.json', []),
            ('sweep_defect_disposition.py', 'defect-disposition-diagnostic.json', ['--csv-out', 'csv/results.csv', '--svg-out', 'figures/actions.svg']),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for script, scenario, args in cases:
                with self.subTest(script=script):
                    p = subprocess.run([sys.executable, str(ROOT / script), str(ROOT / 'scenarios' / scenario), *args], cwd=tmp, capture_output=True, text=True, timeout=30)
                    self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue((Path(tmp) / 'csv/results.csv').is_file())
            self.assertTrue((Path(tmp) / 'figures/actions.svg').is_file())
