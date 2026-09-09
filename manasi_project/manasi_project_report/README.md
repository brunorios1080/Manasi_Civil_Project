# Manasi engineering project report

For the separate **five-page plain-language version**, open
**manasi_project_report_simple.pdf**. Its editable source is
**manasi_project_report_simple.tex**, and technical words are explained where
they appear. Rebuild it with `sh build_simple_report.sh`. This version needs
no external figures or table files.

Open **manasi_project_report.pdf** to read the report. Edit
**manasi_project_report.tex** to change the text.

The report covers the project idea, engineering goals, site assumptions,
hydrology and outlet equations, numerical implementation, design selection,
simulation results, verification, sensitivity, limitations, and conclusions.
It includes all 24 design alternatives and a reproducibility appendix.

## Compile the LaTeX

From this folder:

```sh
sh build_report.sh
```

The script runs pdfLaTeX three times to resolve the contents, citations, and
cross-references. It writes the finished PDF alongside the main `.tex` file
and keeps intermediate files in `build/`. A standard TeX Live or MacTeX
installation with the packages named in the LaTeX preamble is sufficient.

For an online LaTeX editor, upload the entire folder and select
`manasi_project_report.tex` as the main document with pdfLaTeX as the compiler.
The figures and tables use relative paths; no parent project files are needed
to compile the report.

## Evidence and editing

- `figures/`: four vector PDF figures copied from the completed project.
- `tables/`: LaTeX tables generated directly from the copied numerical results.
- `source_data/`: the result tables, configuration, verification records, and
  provenance supporting this report's September 8, 2026 snapshot.
- `generate_tables.py`: rebuilds the tables from `source_data/` using only
  Python's standard library: `python3 generate_tables.py`.
- `build/`: LaTeX logs and report validation records.

This is an expanded report based on the existing completed run. The original
model and original brief `engineering_report.tex` remain in the project root.
`run_project.py` regenerates the original deliverables; it does not automatically
rewrite this expanded report. If the engineering inputs or results change,
update the evidence, figures, tables, and written interpretation together.

The recorded project run passed 16 numerical tests. The tests were rerun
successfully during report preparation, and all current project source hashes
matched the saved run manifest. The full scenario sweep was not rerun to prepare
this document. Existing artifact audits concern the original project outputs;
the new report's build and layout checks are separate.

The report retains the project's contribution record: Codex developed the
technical implementation and documentation; Manasi's individual review and
hands-on contributions remain to be recorded in `MANASI_REVIEW.md`.
