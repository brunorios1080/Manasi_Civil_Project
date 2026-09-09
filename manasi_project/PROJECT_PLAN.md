# Parking-Lot Stormwater Detention: Simulation and Design Comparison

Status: technical study completed on September 8, 2026. The numerical model,
design comparison, verification, dashboard, workbook, drawings, report, and
learning materials have been built and run successfully. Findings are recorded
in [FINDINGS.md](FINDINGS.md); [README.md](README.md) explains the one-command run.
The full rerun reproduced the saved numerical results exactly, excluding runtime
measurements. Manasi's own exercises and personal review remain pending in
[MANASI_REVIEW.md](MANASI_REVIEW.md). The original project scope below is retained
as the specification; actual assistance is recorded in [CONTRIBUTIONS.md](CONTRIBUTIONS.md).

## Project question

For a hypothetical small parking lot, what is the smallest tested detention
storage capacity that reduces peak discharge by at least 50% during a chosen
storm, avoids overflow, and drains back down within 24 hours?

The 50% and 24-hour targets are educational design objectives selected for this
project. They are not claimed to be local drainage requirements. The finished
work will be a conceptual engineering study with a working numerical model,
documented assumptions, independently checked calculations, and a design
recommendation. No field survey or measured rainfall-runoff data is assumed.

## Why this fits Manasi

| Resume background | Project contribution |
| --- | --- |
| Python, intermediate | Run and examine an event simulation; compare design alternatives. |
| Excel, advanced | Independently check runoff volume and storage calculations; compare results. |
| Fluid Dynamics and Numerical Methods | Understand continuity, outlet flow, time stepping, and numerical error. |
| Surveying and AutoCAD coursework | Read and refine a dimensioned conceptual site plan and basin section. |
| Interest in sustainable infrastructure and water systems | Explain how temporary storage changes the timing and peak of stormwater discharge. |

Hydrology concepts such as a curve number and a hydrograph will be new learning
material. The learning guide will explain them using the project's own plots.
An AutoCAD-compatible drawing can be generated without requiring AutoCAD on
this Mac; any later description of her CAD work should reflect the edits she
actually makes.

## A small, fixed scope

Use one hypothetical 80 m by 50 m parking lot, one adjacent 20 m by 10 m
detention footprint, one catchment outlet, and one controlled basin outlet.
The study site is therefore 4,200 m² in all alternatives.

The parking lot contributes 4,000 m² of rainfall-runoff. The reserved 200 m²
footprint receives rainfall directly. To keep the comparison consistent,
the baseline represents this same footprint as an impervious collection pad
with negligible storage or loss; its rainfall drains directly downstream.
In detention cases, that rainfall enters basin storage. All cases consequently
receive the same prescribed inflow volume and use the same downstream
comparison point.

| Input | Starting assumption |
| --- | --- |
| Parking catchment area | 4,000 m² |
| Basin footprint | Fixed 200 m² |
| Parking-lot curve number | CN = 98, an explicit preliminary modeling assumption |
| Initial abstraction | 0.2 times potential retention |
| Catchment lag | 10 minutes; later test 5 and 15 minutes |
| Event rainfall depths | 25, 50, and 100 mm |
| Event duration | 60 minutes |
| Rainfall distributions | Uniform, front-loaded, and back-loaded; each integrates to its stated depth |
| Candidate storage depths | 0.15, 0.30, 0.45, 0.60, 0.75, and 0.90 m |
| Candidate capacities | 30, 60, 90, 120, 150, and 180 m³ |
| Candidate square outlet openings | 40, 60, 80, and 100 mm side lengths |
| Outlet discharge coefficient | 0.62, an assumed value; test sensitivity |
| Initial storage | Empty at the start of each independent event |
| Basin infiltration and evaporation | Zero in the core model |
| Initial reporting step | 30 seconds; refine for convergence checks |
| Simulation horizon | 30 hours; extend if drainage or the inflow tail is incomplete |

The nine storms are synthetic scenarios, not assigned return periods or
observed Pflugerville storms. This avoids a dependency on site data and keeps
the first version reproducible offline. The assumptions can be replaced later
without rewriting the model.

The basin initially uses a constant-area stage-storage approximation,
V = A h. The drawing must identify this idealization. Side-slope geometry,
freeboard, soil investigations, pipe networks, tailwater/backwater, water
quality, and structural details are outside this first study's design claims.

## Simulation method

### 1. Generate the rainfall event

Construct a time series of rainfall increments. Verify that their sum exactly
matches the selected event depth. Front- and back-loaded storms will use
documented block weights with the same duration and total depth as the
uniform storm. Save all inputs with each result.

### 2. Calculate runoff depth from cumulative rainfall

Use the NRCS/SCS curve-number event model. With P and S in millimeters:

```text
S = 25400 / CN - 254
Ia = 0.2 S
Pe(P) = 0                          when P <= Ia
Pe(P) = (P - Ia)^2 / (P - Ia + S)  when P > Ia
```

Compute each interval's excess rainfall by differencing cumulative Pe, then
convert it to runoff volume using the parking-lot area. Do not restart the
initial loss every time step or apply a second impervious-area adjustment
to the same catchment. This is an event model, with state reset between
independent storms. The equations and event-use limitation are documented
in the [USACE SCS Curve Number Loss Model](https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/canopy-surface-infiltration-and-runoff-volume/infiltration/scs-curve-number-loss-model).

As an initial hand-check example, 50 mm rainfall at CN 98 gives approximately
44.28 mm of parking-lot runoff, or 177.10 m³ from 4,000 m². Another 10 m³ of
rain falls on the fixed detention footprint. These are illustrative volume
calculations, not a simulated peak reduction or a completed design result.

### 3. Convert excess rainfall to a runoff hydrograph

Convolve the interval runoff volumes with a documented SCS dimensionless unit
hydrograph using the chosen lag. Store the reference ordinates and their source
with the project. Normalize the discrete response so the total routed volume
equals the input volume, and retain its full recession tail.

This produces flow versus time at the catchment outlet. The role of lag and
the dimensionless hydrograph is described in the
[USACE SCS Unit Hydrograph Model](https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/transform/scs-unit-hydrograph-model).

A peak-only calculation cannot supply the inflow volumes and timing required
for detention routing. This distinction follows
[TxDOT's runoff-method selection guidance](https://www.txdot.gov/manuals/des/hyd/chapter-4--hydrology/section-7--selection-of-the-appropriate-method-for.html).

### 4. Route the water through detention storage

Solve conservation of water volume:

```text
change in storage / change in time
  = parking-lot inflow + direct basin rainfall
    - controlled outlet discharge - overflow discharge
```

Use a level-pool model with a monotonic storage-outflow relationship and
nonnegative storage. The control outlet is an idealized rectangular opening
at the basin floor, discharging freely with no tailwater influence.

For a simple opening-aware rating curve, integrate the idealized orifice
velocity over the wetted opening. If h is water depth above the sill, b is
opening width, and a is opening height, all in meters:

```text
Qout(h) = (2/3) Cd b sqrt(2g) [h^(3/2) - max(h-a, 0)^(3/2)]
```

This is the project's idealized rating curve with a constant assumed Cd,
not a calibrated outlet rating or a claim of exact HEC-HMS equivalence. It
approaches zero at an empty basin and accounts for changing wetted opening
height. Check representative deep-water values against the conventional
orifice equation using head above the opening centroid.

The general use of storage relationships and outlet equations is described
by [USACE reservoir-modeling concepts](https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/reservoir-modeling/reservoir-modeling-concepts-and-equations).
The implementation must not silently use a fully submerged pipe-orifice
formula at all water depths; the restriction is explicit in the
[USACE outlet documentation](https://www.hec.usace.army.mil/confluence/hmsdocs/hmsum/latest/reservoir-elements/outflow-structures-routing).

Use an implicit mass-conserving step, solving its scalar storage equation
with a bracketed root finder. Once capacity is reached, record excess volume
as overflow to the same downstream outlet. Overflow is an accounting boundary,
not a modeled spillway or an inundation map. Never discard clipped water.

### 5. Compare and select designs

Start with the baseline and three representative basin capacities. Then
evaluate all 24 combinations of six depths and four opening sizes against
all nine storms: 216 routed candidate-event cases plus the baseline events.

For each case report peak downstream discharge, peak reduction, time to peak,
maximum storage/depth, overflow volume, total discharged volume, residual
storage, and drawdown time. Downstream discharge includes both the controlled
outlet and overflow.

Select the lowest-capacity tested design that satisfies all three 50 mm
storm-shape cases:

- At least 50% lower peak downstream discharge than the matching baseline.
- No overflow beyond the numerical tolerance.
- Storage below 1% of capacity within 24 hours after rainfall ends, remaining
  below that threshold for the rest of the simulated event.

Use 25 and 100 mm events to show performance outside the selected design event.
Report an infeasible search honestly if no candidate meets the targets; do not
change the targets silently. If several designs tie on capacity, compare their
drawdown and overflow behavior and explain the final choice.

Detention with zero infiltration delays runoff; it does not eliminate its
volume. The same event's total input must eventually emerge as controlled
discharge, overflow, or residual storage. Any quoted benefit in the core
project is a peak-flow or timing benefit.

## Verification and completion criteria

1. **Independent volume check:** Excel formulas reproduce the runoff-volume
   calculation and a simple storage case, rather than merely importing Python
   answers.
2. **Water balance:** runoff generation, hydrograph transformation, and basin
   routing each close their water balance. The project acceptance target is
   less than 0.1% relative error for nonzero storms, with an explicit small
   absolute tolerance for zero-flow cases.
3. **Time-step convergence:** repeat representative and winning cases at 30,
   15, and 7.5 seconds. Target less than 1% change in peak flow and maximum
   storage between the final two resolutions; refine further if needed.
   Check overflow onset/volume and drawdown time separately.
4. **Boundary cases:** zero rainfall/empty basin, rainfall below initial
   abstraction, blocked outlet, insufficient storage, and basin drainage
   without additional inflow behave as expected.
5. **Hydrograph check:** a single pulse preserves volume and has the expected
   response timing; include the complete tail in integration.
6. **Sensitivity:** rerun the selected design at CN 95/98/100, lag 5/10/15 min,
   and Cd 0.50/0.62/0.75, varying one assumption at a time. These are illustrative
   uncertainty bounds, not measured local parameter ranges.
7. **Reproducibility:** one command regenerates the results and all source data
   are local. Record package versions and actual runtime on this Mac.
8. **Report consistency:** every reported metric and annotated figure is
   generated from saved outputs. A recommendation remains conditional on the
   model's assumptions and is not described as field-validated.

These checks verify the calculations and implementation. Calibration against
an actual drainage site is not possible without observations.

## Deliverables

| File or output | What it demonstrates |
| --- | --- |
| `run_project.py` and small model modules | Reproducible simulation, scenario comparison, and validation. |
| `inputs/` and `results/` | Explicit assumptions, reference hydrograph ordinates, and machine-readable results. |
| `stormwater_dashboard.html` | Offline interactive rainfall, flow, and water-depth plots; selectors for tested cases. |
| `stormwater_calculations.xlsx` | Input sheet, independent formula checks, scenario table, and labeled charts. |
| `site_plan.svg` and `site_plan.dxf` | Dimensioned conceptual site layout, drainage arrows, basin footprint, and section. |
| `engineering_report.tex` and `.pdf` | Approximately 4–6 pages: problem, methods, assumptions, verification, results, recommendation, and limitations. |
| `LEARNING_GUIDE.md` | Explanations, worked examples, and questions tied to the actual simulation. |
| `README.md` | Environment setup, one-command run, model scope, and output guide. |

The dashboard will embed its plots and data so it can be viewed without a
server or internet connection. Selecting among computed scenarios is enough
for the first version; arbitrary new parameters are supplied through a local
configuration file and recomputed in Python.

## M1 feasibility and build sequence

The local `psrc` Python environment was checked: it runs natively as `arm64`
and already contains NumPy, pandas, SciPy, Matplotlib, Plotly, and openpyxl.
pdfLaTeX is also installed and has successfully compiled the resume. There
is no GPU or cloud-compute requirement. The model stores a few time series
per event, with scalar routing and a small parameter grid.

Individual cases should be lightweight on this Mac; actual seconds per case,
batch runtime, and memory use will be measured during implementation rather
than treated as benchmarked already. The project will have its own recorded
dependencies and documented environment; installing an engineering desktop
package is not a prerequisite.

Build in four bounded passes:

1. **Working numerical core:** inputs, rainfall generator, runoff volume,
   unit hydrograph, storage routing, and first mass-balance/analytical checks.
2. **Engineering comparison:** candidate sweep, design selection, drawdown,
   overflow, convergence, and sensitivity results.
3. **Portfolio outputs:** interactive plots, formula-based workbook,
   conceptual drawings, and LaTeX report.
4. **Learning and review:** walkthrough, Manasi's own parameter experiment,
   written interpretation, and a final reproducibility run.

The assistant can implement, debug, run, verify, and package passes 1–3.
Plan roughly three 60–90 minute learning sessions for Manasi, adjusted to her
comfort with Python and hydrology. She will check a worked example, change
at least one meaningful design assumption, compare the resulting behavior,
and write her own reason for selecting a design. The final report should
identify assistance and her actual contributions.

## Resume outcome after completion and review

Suggested project title: **Stormwater Detention Modeling and Design Study**.

The final bullets will describe what Manasi actually completed and use metrics
from the saved results. For example, after she runs the scenarios and performs
the comparison herself:

- Evaluated 24 detention configurations across nine synthetic storms using a
  Python rainfall-runoff model; compared peak discharge, storage demand, and
  drawdown behavior.
- Verified runoff and storage calculations in Excel and documented the selected
  design in an engineering report and dimensioned conceptual layout.

The final count and tools must match the finished work. Add a numerical peak
reduction only after obtaining the result, along with the storm and modeling
context. The current resume should not describe this planned project as
completed.

## Optional later extension

After the core study is complete, choose just one: replace synthetic rainfall
with documented location-specific design inputs, add a calibrated infiltration
scenario, or cross-check one case in another hydrologic model. These are outside
the initial completion requirements and do not delay a finished first project.
