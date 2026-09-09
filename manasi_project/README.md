# Stormwater detention modeling and design study

A completed, assistant-generated conceptual study of a hypothetical parking lot.
The nominal selection is **150 m³, 0.75 m deep, with a 100 mm square opening**. Read [FINDINGS.md](FINDINGS.md) for
the results, limitations and sensitivity failures. Manasi's own review is pending.

## Run the complete project

On this Mac, the existing `psrc` environment contains the dependencies:

```sh
conda run -n psrc python run_project.py
```

Or use `/Users/bruno/miniconda3/envs/psrc/bin/python run_project.py`.
The script uses its own location for default paths; running from another directory
is supported. It makes no internet requests. pdfLaTeX must be on PATH or at the
MacTeX default `/Library/TeX/texbin/pdflatex`. The actual runtime and package
versions are in [results/run_manifest.json](results/run_manifest.json).

For a fresh environment, use Python 3.11 or newer and install `requirements.txt`.
Install a TeX distribution containing pdfLaTeX for the report. All model inputs
and the reference hydrograph are local. The default run overwrites generated
outputs but preserves `MANASI_REVIEW.md` and `CONTRIBUTIONS.md` once created.

## Open the deliverables

| File | Use |
| --- | --- |
| [FINDINGS.md](FINDINGS.md) | Main result, failure cases, sensitivity, verification and actual runtime. |
| [stormwater_dashboard.html](stormwater_dashboard.html) | Open directly in a browser; all 216 cases and baselines are embedded. No server or internet required. |
| [stormwater_calculations.xlsx](stormwater_calculations.xlsx) | Independent formulas, storage bisection check, scenario tables and charts. |
| [engineering_report.pdf](engineering_report.pdf) | Six-page engineering report; editable LaTeX source is alongside it. |
| [site_plan.svg](site_plan.svg), [site_plan.dxf](site_plan.dxf) | Dimensioned conceptual plan and section; DXF units are metres, one unit per metre. |
| [site_plan.pdf](site_plan.pdf) | Convenient printable copy of the drawing. |
| [LEARNING_GUIDE.md](LEARNING_GUIDE.md) | Worked examples and three learning sessions. |
| [MANASI_REVIEW.md](MANASI_REVIEW.md) | Preserved workspace for Manasi's own experiment and interpretation. |
| [CONTRIBUTIONS.md](CONTRIBUTIONS.md) | Assistance and actual contribution record. |

## Model and saved data

`inputs/config.json` defines geometry, storms, targets and sensitivity values.
The baseline receives parking runoff plus direct rainfall on the same reserved
footprint used by detention. The model applies cumulative CN losses once per
event, convolves interval runoff with a volume-normalized SCS response, then
routes storage with an implicit bracketed solution and explicit overflow.

The sweep repeats the entire grid at successively halved time steps until at
least three resolutions have been tested and the final peak/storage changes are
below 1%, with stable event decisions and selection. Default output uses
1.875 s after testing 30, 15, 7.5, 3.75, 1.875 s.
The horizon starts at 30 h and doubles, up to the configured cap, if the final
drainage crossing has not occurred. The entire inflow tail is retained.

- `results/scenarios.csv`: final candidate metrics; SI units are in column names.
- `results/baselines.csv`: matching event inputs and baseline peaks.
- `results/design_selection.csv` and `selection.json`: fixed-rule design decision.
- `results/convergence.csv` and `cases_dt*s.csv`: all refinement comparisons.
- `results/sensitivity.csv`: one-at-a-time selected-design scenarios.
- `results/timeseries/*.npz`: complete final arrays, one file per candidate/event.
- `results/timeseries/*.json`: per-case inputs/metrics; shared geometry and criteria are in `config_used.json`.
- `results/sensitivity_series/`: corresponding sensitivity arrays and metadata.
- `results/source_inputs/`, `config_used.json`: exact local inputs used by the run.
- `results/test_results.txt`, `independent_checks.json`, `artifact_audit.json`: verification evidence.

NPZ array lengths: rainfall, runoff amounts and flow arrays have N interval
values; `time_edges_s` and `storage_m3` have N+1 state values. Flows are interval
averages and use midpoint timestamps. Storage is evaluated at boundaries.
Integrate flows by **sum × dt**, not trapezoidal integration of midpoint samples.
Drawdown is measured after rainfall end, at the last crossing below the capacity
fraction; it does not mean mathematically exact emptying.

## Change an assumption

Copy `inputs/config.json` to a new local JSON file, change one value, and run:

```sh
conda run -n psrc python run_project.py --config inputs/my_experiment.json --output-dir experiments/my_experiment
```

The original generated results remain available for comparison. If changing an
area, also change its length/width so the drawing remains consistent. Nonzero
basin infiltration, evaporation and initial storage are intentionally rejected
in the core event study. Use the lower-level routing API for boundary tests.

For development, `--model-only` runs calculations and checks; `--artifacts-only`
rebuilds portfolio files from saved results whose configuration must match.
`python -m unittest discover -s tests -v` runs just the numerical boundary tests.

Workbook green cells contain live formulas with evaluated caches. The saved
formulas are independently re-evaluated during artifact verification. Manual
Excel or AutoCAD use is not claimed. Imported scenario tables and charts are
snapshots: edit JSON and rerun Python to change the full engineering study.

The scientific figures and report read saved result tables and arrays. Dashboard
curves are sampled for compactness while preserving peaks, overflow transitions
and the drainage crossing; numerical metrics always use the full record.

## Scope

Synthetic storms have no assigned return periods. This is a constant-area,
free-discharge, zero-infiltration conceptual comparison. Its capacity does not
include designed freeboard, side slopes, walls, pipe networks or a spillway.
It is not field-calibrated and establishes no local regulatory compliance.
The project explains timing and peak-flow benefits, not eliminated runoff volume.
