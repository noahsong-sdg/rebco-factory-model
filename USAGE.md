# Running the examples

Python 3.11 or newer; no third-party dependencies. Run from this directory:

```sh
python3 run_model.py scenarios/illustrative_baseline.json
python3 run_defect_simulation.py scenarios/illustrative_clustered_defects.json
python3 compare_defect_models.py scenarios/piece-yield-diagnostic.json
python3 run_defect_disposition.py scenarios/defect-disposition-diagnostic.json
python3 sweep_defect_disposition.py scenarios/defect-disposition-diagnostic.json --csv-out outputs/sweep.csv --svg-out outputs/sweep.svg
python3 run_ramp_economics.py scenarios/ramp-cash-diagnostic.json
python3 -m unittest discover -s tests -v
```

Use each script's `--help` for output options. `outputs/` is ignored by Git.
All scenarios are synthetic teaching examples, not manufacturer forecasts.

## Accounting conventions

The factory model charges process variable costs on gross master-web metres
and downstream variable costs on gross slit tape metres before process and
piece retention.
Its headline cost per kA·m allocates all cost to qualified output, whereas the
per-grade cost spreads cost uniformly over **all saleable metres**, including
downgraded output, before converting by that grade's critical current.
These allocation bases are intentionally different and are labeled in reports.

The separate ramp model charges variable cost on **shipments only**. It omits
cost on rejected or unsold production and is not a direct financial extension
of the factory model. Do not join their outputs as if the cost bases matched.

The disposition sweep deliberately replaces the scenario's confirmation cost
with sensitivity cases 0.08 and 0.10; each CSV row and SVG band labels its cost.
The Poisson analytic yield is an infinite-roll expectation; finite-roll
simulation additionally loses short end pieces.
