# Manasi Civil Project

Manasi Emilia Thapa's conceptual stormwater detention study, interactive results
dashboard, engineering reports, and civil engineering resume.

**Live dashboard:** https://manasi-stormwater-study.vercel.app

## Project

The study compares 24 detention designs across nine synthetic storms
(216 scenarios) for a hypothetical 4,000 m² parking lot. The selected 150 m³
storage capacity and 100 mm square outlet produce modeled peak-flow reductions
of 63–74%, zero overflow, and drawdown within 7.9 hours across the three nominal
50 mm storm profiles. Larger storms and sensitivity cases show the design's
limits; these are conceptual results, not a construction design.

Manasi conceived and planned the project, with a programmer assisting with
program execution, as confirmed by the project owner. The technical assistance
record and pending individual review are retained in the project documentation.

## Files

- [Project guide and run instructions](manasi_project/README.md)
- [Findings and limitations](manasi_project/FINDINGS.md)
- [Model source](manasi_project/stormwater/) and [tests](manasi_project/tests/)
- [Saved numerical results](manasi_project/results/)
- [Engineering report](manasi_project/engineering_report.pdf)
- [Extended report](manasi_project/manasi_project_report/)
- [Excel calculations](manasi_project/stormwater_calculations.xlsx)
- [Offline dashboard](manasi_project/stormwater_dashboard.html)
- [Vercel deployment files](vercel-dashboard/) and [deployment instructions](manasi_project/DEPLOYMENT.md)
- [Resume PDF](Manasi_Thapa_Resume_Portrait.pdf) and [editable LaTeX source](Manasi_Thapa_Resume.tex)

## Run the study

From `manasi_project`, install the packages in `requirements.txt`, then run:

```sh
python run_project.py
```

The full artifact build also requires pdfLaTeX. See the project guide for
environment requirements, model-only execution, and reproducibility checks.

## Compile the resume

From the repository root, run twice:

```sh
pdflatex -interaction=nonstopmode -halt-on-error Manasi_Thapa_Resume.tex
```

The resume uses US Letter portrait pages and includes a clickable dashboard link.
Local credentials, caches, and intermediate build files are excluded from Git.
