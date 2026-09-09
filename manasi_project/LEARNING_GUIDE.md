# Learning guide

This guide uses the actual saved study. The technical implementation was generated
with Codex assistance. Use `MANASI_REVIEW.md` to document what you personally check,
change and explain. Allow three 60–90 minute sessions, adjusted to your pace.

## Session 1: rainfall becomes runoff

Open the dashboard with 50 mm rainfall, then switch among
the three shapes. A **hyetograph** shows rainfall intensity; a **hydrograph** shows
flow over time. Millimetres describe a depth, mm/hour a rate, m³ a volume and
m³/s a volumetric flow. A high rainfall block does not make the downstream peak
instantaneous because runoff takes time to arrive.

The curve number is a compact event-loss assumption. Here CN 98
gives S = 25400/CN − 254 = 5.183673 mm and Ia = 0.2S
= 1.036735 mm. Substitute 50 mm
of cumulative rain in (P − Ia)²/(P − Ia + S). The result is
44.275843 mm of excess depth,
or 177.103371 m³ over 4000 m².
Direct rainfall over the 200 m² footprint contributes
10.000000 m³. Total input is 187.103371 m³.

Reproduce this with a calculator and the workbook's `Runoff checks` sheet.
Column H is a Python reference; columns B–G are formulas you can inspect.
Initial abstraction is applied once to cumulative rain, not subtracted again
at each time step. For CN 100, S and Ia are zero and runoff equals rainfall.

The **unit hydrograph** is the timing response to a unit amount of runoff.
In `inputs/scs_dimensionless_uh.csv`, both columns are ratios. A lag of
10 minutes controls response timing; it is not another loss.
The model normalizes the response to preserve volume and keeps its whole tail.

Write your answers: Why do equal-depth storm shapes produce the same event
volume but different peaks? Why is the direct footprint rain included even when
CN losses make parking runoff zero? Why would a peak-only runoff estimate be
insufficient to size detention storage?

## Session 2: storage and outlet tradeoffs

Start with the workbook's `Storage check`. A blocked 20 m³ tank receives 1 m³/s
for 40 seconds. It ends with 20 m³ stored and 20 m³ overflow. Storage clipping
does not remove the excess water. Next inspect `Implicit step`: each spreadsheet
row halves a bracket until storage and outlet discharge balance the available
water. Compare the final spreadsheet storage with its Python reference.

Open the default selected design: **150 m³, 0.75 m deep, with a 100 mm square opening**. Its constant-area model
uses V = A h. A larger outlet drains faster but can release a higher peak.
A smaller outlet can improve the controlled peak while increasing storage
demand or overflow. Always inspect **downstream = controlled + overflow**.

Below the opening's top, only part of the outlet is wetted. The integrated
rating approaches zero smoothly as the basin empties. In shallow water its
discharge scales with h^(3/2); the long tail explains why the study defines
drainage at 1% of capacity rather than exactly zero.

Make one meaningful experiment yourself. Copy the JSON file, change only CN
from 98 to 100 (or choose one other parameter), and use `--output-dir` to keep
your results separate. Record your prediction before running. Compare event
input volume, peak reduction, overflow and drawdown afterward. The saved
sensitivity results already show a warning case; explain its cause rather than
copying its numbers alone. One-at-a-time sensitivity does not test all joint
parameter combinations.

Write your answers: Why does high percentage peak reduction not guarantee a
passing design? Why can a larger nominal capacity produce a shorter time to
the 1% threshold even when the storage hydrograph is unchanged? What did your
parameter experiment change in the physics versus only in the criterion?

## Session 3: drawings, verification, and explanation

Read the report and the dimensioned SVG. The parking rectangle is 80 × 50 m
and the adjacent footprint is 20 × 10 m in the default configuration. The
DXF contains metre coordinates; import it with 1 unit = 1 metre. Its basin
section uses true geometry. SVG/PDF plan and section use separate scales.
Vertical basin boundaries illustrate constant area, not engineered walls.

If you use CAD, record the application and the actual edits you make. An SVG
inspection is useful but is not evidence that you authored an AutoCAD drawing.
Explain where grading, side slopes, freeboard and a physical overflow route
would have to be added for a real site design.

Read `results/convergence.csv`: some coarse overflowing cases changed enough
to require more refinement. Water balance by itself does not establish accurate
peaks, and convergence does not establish field validity. The analytical and
spreadsheet checks provide distinct evidence of correct calculations.

Write a 150–250 word interpretation addressing the smallest **tested** feasible
design, the 100 mm overflow limitation, sensitivity to CN, and why detention
delays rather than removes runoff. Describe what you did yourself and what was
assisted. Fill in the review record before using completion claims on a resume.

## Possible resume wording after your own review

Adapt only after the listed actions are personally completed:

- Analyzed 24 detention configurations across nine synthetic storms using a
  Python model developed with AI assistance; interpreted peak discharge,
  storage, overflow and drainage results.
- Independently checked runoff and storage formulas in Excel and reviewed a
  dimensioned conceptual basin layout; documented design assumptions and limits.

Replace or remove any tool/activity you did not actually use. A result metric
must state its synthetic storm and modeling context. Do not describe this study
as field-calibrated, construction-ready or evidence of regulatory compliance.
