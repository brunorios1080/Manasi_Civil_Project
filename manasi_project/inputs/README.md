# Local source inputs

`config.json` is the study specification, including units in key names. All runs
copy the actual configuration and hydrograph/source files into `results/`.
Rainfall shapes are project-defined synthetic six-block events. Each block lasts
10 minutes in the default one-hour storm. Relative weights are `[1,1,1,1,1,1]`,
`[6,5,4,3,2,1]`, and `[1,2,3,4,5,6]`, each divided by its own sum before scaling
to the total rainfall. They have no assigned return period.

`scs_dimensionless_uh.csv` contains all 33 ordinate pairs from
[TxDOT Table 4-29](https://www.txdot.gov/manuals/des/hyd/chapter-4--hydrology/section-13--hydrograph-method/nrcs-dimensionless-unit-hydrograph.html),
accessed September 8, 2026. The columns are dimensionless `t/Tp` and `q/qp`.
The terminal point is `(5,0)`; the nonzero recession before it is retained.
Use the reference table, not the subsequent rounded example table.

The model linearly interpolates the ordinate pairs and analytically integrates
that interpolation over each computational interval. The resulting weights
sum to one. This preserves the supplied runoff volume without using rounded
tabulated amplitudes as dimensional flow. `Tp = lag + dt/2`, measured from the
start of the excess-rainfall pulse. Rainfall and runoff are interval amounts;
reported flow peaks use interval averages and peak times use interval centers.

`sources.json` records the authoritative methodological references and exactly
what each supplied to the study. No network requests occur during a project run.
CN, lag, rainfall, Cd, geometry, and the design criteria remain project assumptions.
