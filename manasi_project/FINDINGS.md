# Findings: parking-lot stormwater detention

Generated from saved numerical outputs. Conceptual engineering analysis completed with assistant support; Manasi's individual review and exercises remain unverified.

## Design finding

The smallest **tested** passing capacity is **150 m³**, with **0.75 m** modeled depth over 200 m² and a **100 × 100 mm** square outlet. It passes every 50 mm storm shape at CN 98, lag 10 minutes, and Cd 0.62.

| Storm shape | Baseline peak (L/s) | Detained peak (L/s) | Reduction | Max storage (m³) | Overflow (m³) | Drawdown after rain (h) |
| --- | --- | --- | --- | --- | --- | --- |
| Uniform | 57.48 | 21.22 | 63.09% | 129.48 | 0.000 | 7.65 |
| Front Loaded | 73.19 | 21.04 | 71.25% | 127.55 | 0.000 | 7.51 |
| Back Loaded | 85.67 | 21.94 | 74.39% | 137.76 | 0.000 | 7.81 |

The drainage criterion is below 1.50 m³ (7.50 mm water depth), remaining below it for the rest of the event. It is measured from rainfall end, not from peak storage. The worst case is 7.806 hours. Maximum design-event depth is 0.6888 m, leaving 12.239 m³ below the nominal accounting capacity. This is not a designed freeboard allowance.

Every lower-capacity candidate fails at least one design shape. At 120 m³, the least-overflowing tested opening (100 mm) still produces 18.459 m³ of worst-case overflow. See [the complete selection table](results/design_selection.csv).

At 150 m³, 1 of 4 openings passes all design shapes. The tie rule is lowest capacity, then shortest worst-case drawdown, then least overflow, then largest opening. Larger tested passing designs are retained in the comparison; their extra capacity is not necessary for the nominal objective.

## Performance beyond the selected design event

| Rain (mm) | Shape | Peak reduction | Overflow (m³) | Discharged by horizon (m³) | Residual (m³) | Horizon (h) |
| --- | --- | --- | --- | --- | --- | --- |
| 25 | Uniform | 54.02% | 0.000 | 83.722 | 0.0840 | 30 |
| 25 | Front Loaded | 61.69% | 0.000 | 83.723 | 0.0831 | 30 |
| 25 | Back Loaded | 67.12% | 0.000 | 83.721 | 0.0848 | 30 |
| 50 | Uniform | 63.09% | 0.000 | 187.012 | 0.0916 | 30 |
| 50 | Front Loaded | 71.25% | 0.000 | 187.013 | 0.0908 | 30 |
| 50 | Back Loaded | 74.39% | 0.000 | 187.011 | 0.0926 | 30 |
| 100 | Uniform | 0.00% | 162.526 | 396.057 | 0.0938 | 30 |
| 100 | Front Loaded | 3.21% | 163.580 | 396.057 | 0.0931 | 30 |
| 100 | Back Loaded | 0.00% | 173.330 | 396.056 | 0.0941 | 30 |

The 100 mm cases exceed the selected storage substantially. The overflow belongs in downstream discharge; omitting it would create a false impression of protection. These depths have no assigned recurrence interval. No spillway hydraulics or flooding extent was modeled.

## Water balance and interpretation

The 50 mm event produces 44.275843 mm of parking runoff, or 177.103371 m³. Direct footprint rainfall adds 10.000000 m³. Each alternative receives **187.103371 m³**. The 4200 m² study area and downstream comparison point are unchanged between alternatives.

Controlled discharge + overflow + remaining storage equals input. Zero basin infiltration and evaporation mean the benefit is delayed timing and reduced peak flow; the model does not remove runoff volume. The low-depth outlet law drains asymptotically, so small horizon residuals are expected and explicitly counted.

| Balance | Largest absolute error (m³) | Largest relative error |
| --- | --- | --- |
| runoff_generation_error_m3 | 1.4211e-14 | 1.6957e-16 |
| transform_error_m3 | 2.8422e-14 | 1.8033e-16 |
| routing_balance_error_m3 | 1.0038e-09 | 5.3648e-12 |

## Numerical verification

All 16 numerical tests passed. They cover zero rainfall, rainfall below initial abstraction (with direct footprint rain still included), CN 100, empty storage, a blocked outlet, capacity exceedance, analytical shallow drainage, pulse volume/timing/tail, and per-step continuity. See [test results](results/test_results.txt) and [independent calculations](results/independent_checks.json).

All 216 candidate cases were repeated at 30, 15, 7.5, 3.75, 1.875 seconds. Final published metrics and time series use **1.875 s**. The largest final peak-flow change is **0.9078%**; maximum-storage change is **0.0342%**. Both are below 1% for the entire grid. Winner selection, event pass/fail, and overflow/no-overflow classification are stable at the final pair.

Final overflow-volume change is at most 0.054714 m³; onset shifts by at most 1.875 s. Drawdown shifts by at most 8.389 s. Earlier 30/15/7.5 s results were insufficient for some overflowing alternatives, which explains the extra refinement. [All convergence checks](results/convergence.csv) are saved.

The workbook has independent CN equations, an exact blocked-storage calculation, and 45 Excel-formula bisection iterations for a controlled-outlet step. Its formula evaluator reopens the saved workbook, evaluates every formula and verifies each cached result. Excel is set to recalculate automatically. A manual Excel session by Manasi is not claimed.

## Sensitivity findings

| Varied parameter | Value | Worst reduction | Worst overflow (m³) | Worst drawdown (h) | Every shape passes |
| --- | --- | --- | --- | --- | --- |
| curve_number | 95 | 64.37% | 0.000 | 7.52 | Yes |
| curve_number | 98 | 63.09% | 0.000 | 7.81 | Yes |
| curve_number | 100 | 47.25% | 2.841 | 7.95 | No |
| lag_min | 5 | 62.47% | 0.000 | 7.71 | Yes |
| lag_min | 10 | 63.09% | 0.000 | 7.81 | Yes |
| lag_min | 15 | 63.40% | 0.000 | 7.90 | Yes |
| discharge_coefficient | 0.5 | 69.16% | 0.000 | 9.72 | Yes |
| discharge_coefficient | 0.62 | 63.09% | 0.000 | 7.81 | Yes |
| discharge_coefficient | 0.75 | 57.01% | 0.000 | 6.42 | Yes |

**Sensitivity failure:** curve_number = 100, back loaded 50 mm storm: 47.255% peak reduction and 2.841 m³ overflow. The nominal recommendation therefore does not pass every tested uncertainty assumption.

Each row changes one parameter only and recomputes the matching baseline; these are not joint worst-case combinations or measured local bounds. Nominal values intentionally repeat in each parameter group.

## Reproducibility and outputs

Machine: `macOS-26.4.1-arm64-arm-64bit-Mach-O`, `arm64`. Python: `3.14.3 | packaged by conda-forge | (main, Feb  9 2026, 22:09:14) [Clang 20.1.8 ]`. The grid contains 24 designs, 9 storms and 216 routed cases; there are 27 sensitivity rows (nominal repeats included). The longest core horizon is 60 h, automatically extended where the 30 h initial horizon did not establish drainage.

Measured study-stage runtime: **301.60 s**. Median final-resolution case: **0.3663 s**; slowest: **1.1556 s**. Recorded full command runtime: **314.25 s**. Peak Python-process memory: **408.52 MiB** (child-process memory excluded). Timing includes the actual execution on this Mac and is not a general hardware benchmark.

Package versions, input snapshots, source hashes and timestamps are in [the run manifest](results/run_manifest.json). [Artifact checks](results/artifact_audit.json) cover saved time-series consistency, workbook formulas, embedded dashboard data, drawings and the PDF. Follow [README.md](README.md) to regenerate everything with one command.

## Scope and unfinished human review

The technical study, calculations, comparisons and portfolio files are assistant-generated. No survey, field calibration, return-period analysis, freeboard design, side-slope design, structural sizing, pipe-network design, tailwater analysis or water-quality benefit is established. The dimensional drawing identifies its constant-area storage idealization.

Manasi still needs to complete the exercises and record her own interpretation in [MANASI_REVIEW.md](MANASI_REVIEW.md). Her manual Excel checks, parameter experiment, CAD edits and resume claims remain pending until she performs them. This work does not invent contributions or sign off on her behalf.

## Sources

Additional verification records from the completed run:
[exact rerun comparison](results/reproducibility_check.json) and
[offline browser, PDF, and DXF review](results/visual_review.json).

- [USACE HEC-HMS Technical Reference: SCS Curve Number Loss Model](https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/canopy-surface-infiltration-and-runoff-volume/infiltration/scs-curve-number-loss-model) — Cumulative event runoff equation, incremental differencing, and event-only limitation. CN 98 is a project assumption. Accessed 2026-09-08.
- [USACE HEC-HMS Technical Reference: SCS Unit Hydrograph Model](https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/transform/scs-unit-hydrograph-model) — Tp = lag + excess-rainfall interval / 2; dimensionless hydrograph interpretation. Accessed 2026-09-08.
- [TxDOT Hydraulic Design Manual: NRCS Dimensionless Unit Hydrograph, Table 4-29](https://www.txdot.gov/manuals/des/hyd/chapter-4--hydrology/section-13--hydrograph-method/nrcs-dimensionless-unit-hydrograph.html) — All 33 time and discharge ordinate pairs in scs_dimensionless_uh.csv, including terminal (5, 0). Table 4-29, not the rounded worked example in Table 4-30. Accessed 2026-09-08.
- [USACE HEC-HMS Technical Reference: Reservoir Modeling Concepts and Equations](https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/reservoir-modeling/reservoir-modeling-concepts-and-equations) — Level-pool continuity and storage/outflow relationships. This project uses backward Euler, not the manual's trapezoidal Modified Puls implementation. Accessed 2026-09-08.
- [USACE HEC-HMS User's Manual: Outflow Structures Routing](https://www.hec.usace.army.mil/confluence/hmsdocs/hmsum/latest/reservoir-elements/outflow-structures-routing) — Outlet submergence limitations. The vertically integrated floor opening with constant Cd is the project's idealized rating, not a copied or calibrated HEC-HMS structure. Accessed 2026-09-08.
- [TxDOT Hydraulic Design Manual: Selection of the Appropriate Method for Calculating Runoff](https://www.txdot.gov/manuals/des/hyd/chapter-4--hydrology/section-7--selection-of-the-appropriate-method-for.html) — Need for an event hydrograph for storage calculations rather than a peak-only runoff estimate. Accessed 2026-09-08.
