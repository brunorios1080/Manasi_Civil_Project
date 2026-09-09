#!/bin/sh
# Compile the separate plain-language version. No external figure files needed.
set -eu
cd "$(dirname "$0")"
mkdir -p build/simple
if command -v pdflatex >/dev/null 2>&1; then
    simple_tex_engine="$(command -v pdflatex)"
elif [ -x /Library/TeX/texbin/pdflatex ]; then
    simple_tex_engine=/Library/TeX/texbin/pdflatex
else
    echo 'pdfLaTeX is required to compile this report.' >&2
    exit 1
fi
for simple_pass in 1 2; do
    if ! "$simple_tex_engine" -interaction=nonstopmode -halt-on-error \
        -file-line-error -output-directory=build/simple \
        manasi_project_report_simple.tex \
        > "build/simple/compile-pass-${simple_pass}.txt" 2>&1; then
        cat "build/simple/compile-pass-${simple_pass}.txt" >&2
        exit 1
    fi
done
cp build/simple/manasi_project_report_simple.pdf manasi_project_report_simple.pdf
echo 'Built manasi_project_report_simple.pdf'
