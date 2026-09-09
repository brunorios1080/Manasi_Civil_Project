#!/bin/sh
# Rebuild the self-contained report with pdfLaTeX; no model rerun is needed.
set -eu
cd "$(dirname "$0")"
mkdir -p build
if command -v pdflatex >/dev/null 2>&1; then
    report_tex_engine="$(command -v pdflatex)"
elif [ -x /Library/TeX/texbin/pdflatex ]; then
    report_tex_engine=/Library/TeX/texbin/pdflatex
else
    echo 'pdfLaTeX is required. Install a TeX distribution and rerun this script.' >&2
    exit 1
fi
for report_pass in 1 2 3; do
    if ! "$report_tex_engine" -interaction=nonstopmode -halt-on-error \
        -file-line-error -output-directory=build manasi_project_report.tex \
        > "build/compile-pass-${report_pass}.txt" 2>&1; then
        cat "build/compile-pass-${report_pass}.txt" >&2
        exit 1
    fi
done
cp build/manasi_project_report.pdf manasi_project_report.pdf
echo 'Built manasi_project_report.pdf'
