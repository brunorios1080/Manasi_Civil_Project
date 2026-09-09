"""Generate the report and written findings from persisted result tables."""
from datetime import date
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pandas as pd


def read_results(root):
    root = Path(root)
    def frame(name):
        try:
            return pd.read_csv(root / "results" / name)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
    return {"cases": frame("scenarios.csv"), "baselines": frame("baselines.csv"),
            "selection_table": frame("design_selection.csv"), "sensitivity": frame("sensitivity.csv"),
            "convergence": frame("convergence.csv"),
            "selection": json.loads((root / "results/selection.json").read_text())}


def tex(value):
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
                    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(c, c) for c in str(value))


def label(shape):
    return shape.replace("_", " ").title()


def fmt(value, digits=2):
    return "not reached" if value is None or pd.isna(value) else f"{value:.{digits}f}"


def md_table(headers, rows):
    return "| " + " | ".join(headers) + " |\n| " + " | ".join(["---"] * len(headers)) + " |\n" + "\n".join(
        "| " + " | ".join(map(str,row)) + " |" for row in rows)


def sensitivity_summary(frame):
    rows = []
    if frame.empty:
        return rows
    for (parameter, value), group in frame.groupby(["varied_parameter", "parameter_value"], sort=False):
        rows.append({"parameter": parameter, "value": value,
                     "minimum_peak_reduction_pct": float(group.peak_reduction_pct.min()),
                     "maximum_overflow_m3": float(group.overflow_m3.max()),
                     "maximum_drawdown_h": float(group.drawdown_h_after_rain.max()),
                     "all_pass": bool(group.all_pass.all())})
    return rows


def build_report(root, config, manifest):
    root = Path(root)
    r = read_results(root)
    selection = r["selection"]
    winner = selection["selected"]
    if winner:
        selected = r["cases"][r["cases"].design_id == winner["design_id"]]
        recommendation = (f"The smallest tested feasible capacity is {winner['capacity_m3']:g} m$^3$: "
            f"{winner['storage_depth_m']:.2f} m modeled storage depth over {config['basin_area_m2']:g} m$^2$, "
            f"with a {winner['outlet_side_mm']:g} by {winner['outlet_side_mm']:g} mm floor opening. "
            f"Across all {config['design_rainfall_mm']:g} mm storm shapes, peak reduction is at least "
            f"{winner['worst_peak_reduction_pct']:.2f}\\%, overflow is zero, and the longest drainage time "
            f"is {winner['worst_drawdown_h']:.2f} h after rainfall ends.")
        figure_identity = winner["design_id"]
    else:
        selected = r["cases"][r["cases"].design_id == r["cases"].sort_values(["capacity_m3","outlet_side_mm"]).iloc[-1].design_id]
        figure_identity = selected.design_id.iloc[0]
        recommendation = "No tested configuration satisfies all three objectives across the design-event storm shapes. The search is infeasible under the stated assumptions; no compliant design is recommended. Figures use the largest tested configuration as an illustrative case."
    design = selected[np.isclose(selected.rainfall_mm, config["design_rainfall_mm"])]
    last_conv = r["convergence"][np.isclose(r["convergence"].fine_dt_s, selection["final_dt_s"])]
    source_rows = json.loads((root / "results/source_inputs/sources.json").read_text())
    assumptions = [
        ("Contributing areas", f"Parking {config['parking_area_m2']:g} m$^2$ + footprint {config['basin_area_m2']:g} m$^2$"),
        ("CN; abstraction; lag", f"{config['curve_number']:g}; $I_a={config['abstraction_ratio']:g}S$; {config['lag_min']:g} min"),
        ("Synthetic rainfall", ", ".join(f"{v:g}" for v in config["rainfall_depths_mm"]) + f" mm; {config['rainfall_duration_min']:g} min; {len(config['rainfall_weights'])} shapes"),
        ("Storage and openings", f"{len(config['storage_depths_m'])} depths $\\times$ {len(config['outlet_sides_mm'])} square openings"),
        ("Initial storage; basin losses", "Empty; zero infiltration and evaporation"),
        ("Outlet coefficient; gravity", f"$C_d={config['discharge_coefficient']:g}$; $g={config['gravity_m_s2']:g}$ m/s$^2$"),
        ("Final numerical resolution", f"{selection['final_dt_s']:g} s; at least {config['horizon_h']:g} h, extended if needed"),
    ]
    assumption_table = "\n".join(a + " & " + b + r" \\" for a,b in assumptions)
    result_rows = "\n".join(
        f"{label(row['shape'])} & {row.baseline_peak_m3_s*1000:.2f} & {row.peak_downstream_m3_s*1000:.2f} & {row.peak_reduction_pct:.2f} & {row.maximum_storage_m3:.2f} & {row.drawdown_h_after_rain:.2f} " + r"\\"
        for _, row in design.iterrows())
    off_rows = "\n".join(
        f"{rain:g} & {max(0,group.peak_reduction_pct.min()):.2f}--{max(0,group.peak_reduction_pct.max()):.2f} & {group.overflow_m3.min():.2f}--{group.overflow_m3.max():.2f} & {group.drawdown_h_after_rain.max():.2f} " + r"\\"
        for rain,group in selected.groupby("rainfall_mm"))
    volume = r["baselines"][np.isclose(r["baselines"].rainfall_mm, config["design_rainfall_mm"])].iloc[0]
    sensitivity_rows = "\n".join(
        f"{tex(row['parameter'].replace('_',' '))} & {row['value']:g} & {row['minimum_peak_reduction_pct']:.2f} & {row['maximum_overflow_m3']:.3f} & {row['maximum_drawdown_h']:.2f} & {'Pass' if row['all_pass'] else 'Fail'} " + r"\\"
        for row in sensitivity_summary(r["sensitivity"]))
    convergence_rows = []
    for fine_dt, group in r["convergence"].groupby("fine_dt_s",sort=False):
        convergence_rows.append(f"{group.coarse_dt_s.iloc[0]:g} $\\to$ {fine_dt:g} & "
            f"{100*group.peak_downstream_m3_s_relative_change.max():.4f} & "
            f"{100*group.maximum_storage_m3_relative_change.max():.4f} & "
            f"{group.overflow_change_m3.max():.4f} & {group.drawdown_change_s.max():.2f} " + r"\\")
    references = "\n".join(r"\bibitem{" + entry["id"] + "}" + tex(entry["title"]) + ". "
        + r"\href{" + entry["url"] + "}{" + tex(entry["id"] + " source link") + "}. Accessed " + entry["accessed"] + "."
        for entry in source_rows)
    balance_error = max(v["absolute_m3"] for v in manifest["max_balance_errors"].values())
    horizon = r["cases"].horizon_h.max()
    basin_fraction_mm = config["drawdown_fraction"] * selected.storage_depth_m.iloc[0] * 1000
    text = r'''\documentclass[10pt,letterpaper]{article}
\usepackage[margin=0.7in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{helvet}
\renewcommand{\familydefault}{\sfdefault}
\usepackage{graphicx,booktabs,amsmath,xcolor,fancyhdr}
\usepackage[colorlinks=true,urlcolor=teal,citecolor=teal,linkcolor=teal]{hyperref}
\definecolor{ink}{HTML}{163640}
\definecolor{teal}{HTML}{117C77}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5pt}
\setlength{\headheight}{14pt}
\setlength{\tabcolsep}{5pt}
\renewcommand{\arraystretch}{1.18}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\small\color{ink}STORMWATER DETENTION MODELING}
\fancyhead[R]{\small Conceptual study}
\fancyfoot[L]{\footnotesize Synthetic inputs; no field calibration}
\fancyfoot[R]{\thepage\ / 6}
\newcommand{\pagetitle}[1]{\vspace*{2pt}{\Large\bfseries\color{ink}#1}\par\vspace{5pt}}
\begin{document}
\pagetitle{Parking-lot detention: a tested design comparison}
{\small Prepared for Manasi's project portfolio. Assistant-generated study; individual review remains pending.}

\textbf{Question.} What is the smallest tested storage that lowers peak downstream discharge by at least __REDUCTION__\%, avoids overflow, and remains below __FRACTION__\% of capacity within __DRAWDOWN__ hours after rainfall ends? These are educational objectives, not local drainage requirements.

\textbf{Finding.} __RECOMMENDATION__

\begin{center}\small
\begin{tabular}{p{0.30\linewidth}p{0.62\linewidth}}\toprule
Input & Assumption \\ \midrule
__ASSUMPTIONS__
\bottomrule\end{tabular}
\end{center}

\textbf{A consistent comparison.} The same __SITEAREA__ m$^2$ contributes in every case. The baseline treats the reserved footprint as an impervious collection pad with negligible storage. Its rainfall discharges directly. Detention cases store that rainfall together with parking runoff. Both streams reach the same downstream accounting point.

\begin{center}\includegraphics[width=.94\linewidth,height=3.65in,keepaspectratio]{site_plan.pdf}\end{center}
{\footnotesize Figure 1. Dimensioned conceptual geometry. The constant-area basin is a storage idealization; walls, grading, freeboard and a physical spillway are not designed. Editable SVG and metre-coordinate DXF are included.}
\newpage
\pagetitle{Method and reproducible assumptions}
\textbf{Rainfall and event losses.} Project-defined block shapes share one duration and total depth. Each shape divides the event into equal-duration blocks with relative weights: __RAINWEIGHTS__. Each vector is normalized by its sum. Block boundaries are integrated exactly even if a computational interval crosses a boundary.

For cumulative precipitation $P$ and retention $S$ in millimetres, the event CN calculation is\cite{cn}
\[
S=25400/CN-254,\qquad I_a=__ABSTRACTION__S,\qquad
P_e(P)=\begin{cases}0&P\leq I_a,\\(P-I_a)^2/(P-I_a+S)&P>I_a.\end{cases}
\]
Incremental runoff is the difference between successive cumulative $P_e$ values. It is multiplied by parking area and divided by 1,000 to obtain m$^3$. CN 100 is handled explicitly as $P_e=P$, including $P=0$. Loss state resets between independent events. No second impervious-area adjustment is made.

\textbf{Hydrograph transformation.} The 33 local reference ordinates are from TxDOT Table 4-29.\cite{ordinates} Set $T_p=t_{lag}+\Delta t/2$, relative to the beginning of an excess-rainfall pulse.\cite{uh} Integrate the piecewise-linear dimensionless curve over every output interval to form nonnegative volume fractions $w_j$ with $\sum_j w_j=1$. Convolve those fractions with runoff volumes; divide by $\Delta t$ to obtain interval-average flow. Retain the complete reference tail through $5T_p$. The lag is assumed, not estimated from a surveyed flow path. A hydrograph supplies both timing and volume needed for detention.\cite{selection}

\textbf{Storage and outlet.} Use $V=A_bh$ with fixed area. The project's free-discharge square opening has side $a$ and sill at the floor. Integrating local velocity over the wetted opening gives
\[
Q(h)=\int_0^{\min(h,a)} C_da\sqrt{2g(h-z)}\,dz
=\tfrac23 C_da\sqrt{2g}\,[h^{3/2}-\max(h-a,0)^{3/2}].
\]
This expression includes partial wetting near an empty basin. It is an idealization with constant $C_d$, not a calibrated HEC-HMS rating. The fully wetted approximation uses centroid head, $C_da^2\sqrt{2g(h-a/2)}$; it is not used below submergence.\cite{outlet}

\textbf{Implicit continuity.} For an interval input volume $I_n$, solve
\[
V_{n+1}+\Delta t\,Q(V_{n+1}/A_b)=V_n+I_n
\]
with a bracketed Brent root solver on $[0,\min(V_{max},V_n+I_n)]$. If the available volume exceeds $V_{max}+\Delta t\,Q(V_{max}/A_b)$, fix storage at capacity and count the excess as overflow. Controlled discharge plus overflow is downstream flow. This is backward Euler; it uses the level-pool conservation concept but is not the manual's trapezoidal Modified Puls algorithm.\cite{routing}

\textbf{Reporting conventions.} Flow peaks are maxima of interval-average flow; peak times are interval centers. Depth and storage use step-boundary states. Overflow onset is the beginning of its first interval. Drawdown is the final interpolated crossing below the capacity fraction, minus rainfall end time, with no later rebound. Any remaining horizon storage is retained in the water balance. Small outlets triggered horizon extension up to __HORIZON__ hours. Exact emptying is asymptotic for this rating; ``drained'' means below the stated threshold.
\newpage
\pagetitle{Candidate comparison and selected-event results}
The search evaluates __CANDIDATES__ storage--opening configurations over __EVENTS__ synthetic storms (__CASES__ routed cases plus matching baselines). Every design-event shape must meet all three objectives. Rank passing designs by capacity, then shortest worst-case drawdown, then overflow, then opening size. __RECOMMENDATION__

\begin{center}\small
\begin{tabular}{lrrrrr}\toprule
Shape & Baseline & Downstream & Reduction & Max. storage & Drawdown \\
 & L/s & L/s & \% & m$^3$ & h after rain \\\midrule
__RESULTROWS__
\bottomrule\end{tabular}\end{center}

\begin{center}\includegraphics[width=.86\linewidth,height=2.9in,keepaspectratio]{results/figures/design_comparison.pdf}\end{center}
{\footnotesize Figure 2. Cell colour shows the worst peak reduction for the design storms. PASS requires peak, overflow and drainage criteria together. A high percentage alone is insufficient.}

\textbf{Why smaller alternatives fail.} __SMALLER__

\textbf{Outside the design event.} These are stress scenarios with no assigned return periods. The selected geometry is not resized between events.
\begin{center}\small\begin{tabular}{rrrr}\toprule
Rainfall (mm) & Peak reduction range (\%) & Overflow range (m$^3$) & Longest drawdown (h) \\\midrule
__OFFROWS__
\bottomrule\end{tabular}\end{center}

The 100 mm results demonstrate finite storage limits. When the basin fills, accounting overflow can dominate downstream discharge. Overflow is not a modeled spillway flow or an inundation prediction.
\newpage
\pagetitle{Hydrographs, water depth, and the drainage tail}
\begin{center}\includegraphics[width=\linewidth,height=4.0in,keepaspectratio]{results/figures/design_hydrographs.pdf}\end{center}
{\footnotesize Figure 3. Full-resolution design-event curves for __FIGUREIDENTITY__. Rainfall generates a delayed inflow hydrograph; storage and controlled discharge rise together. Dashed depth marks capacity.}

The __DESIGNRAIN__ mm event supplies __PARKVOLUME__ m$^3$ of parking runoff plus __DIRECTVOLUME__ m$^3$ of direct footprint rainfall, or __TOTALVOLUME__ m$^3$ in total. Detention does not eliminate this runoff volume. At the end of each run, controlled discharge + overflow + residual storage reproduces total input within numerical tolerance.

\begin{center}\includegraphics[width=\linewidth,height=2.6in,keepaspectratio]{results/figures/drawdown_and_overflow.pdf}\end{center}
{\footnotesize Figure 4. The drainage threshold corresponds to __THRESHOLDMM__ mm of water over the fixed area for the illustrated design. Near the floor the partly wetted outlet produces a long, low-flow tail. The right plot shows excess water once storage is exhausted.}
\newpage
\pagetitle{Verification and sensitivity}
\textbf{Independent calculations.} __TESTS__ automated tests cover zero and sub-abstraction rainfall, CN 100, blocked outlets, insufficient storage, full-tail unit-hydrograph timing and volume, and water balance at each step. The outlet integral also matches independent numerical quadrature. For shallow drainage, $Q=kh^{3/2}$ gives the exact no-inflow solution
\[
h(t)=\left[h_0^{-1/2}+kt/(2A_b)\right]^{-2},\qquad k=\tfrac23 C_da\sqrt{2g}.
\]
The numerical solution approaches this limit under step refinement. The workbook separately evaluates CN volume formulas, an exact blocked-storage fixture, and 45 spreadsheet bisection iterations for one controlled-outlet step. Formula caches are re-evaluated from the saved Excel formulas; no manual Excel review is claimed.

\textbf{Water balance.} The largest absolute discrepancy across generation, transformation and routing in the nominal and sensitivity cases is __BALANCEERROR__ m$^3$. The acceptance tolerance is 0.1\% relative plus $10^{-8}$ m$^3$ absolute. End storage is never silently discarded.

\begin{center}\small\begin{tabular}{rrrrr}\toprule
Steps (s) & Max. peak change (\%) & Max. storage change (\%) & Max. overflow change (m$^3$) & Max. drawdown change (s) \\\midrule
__CONVERGENCEROWS__
\bottomrule\end{tabular}\end{center}
{\footnotesize Changes are maxima across the complete candidate grid, not only the winner. The final two resolutions satisfy the 1\% target for peak and storage; selection and pass/fail decisions are stable. Maximum final overflow-onset movement is __ONSETCHANGE__ s. Overflow volume and drawdown differences are reported separately above.}

\textbf{One-at-a-time uncertainty.} The selected geometry is held fixed. Each parameter value is run through all design-event shapes; baseline runoff is recomputed with that parameter. The table reports the worst value for each metric, which may occur in different shapes. The nominal scenario repeats in each parameter group.
\begin{center}\small\begin{tabular}{lrrrrl}\toprule
Varied parameter & Value & Min. reduction (\%) & Max. overflow (m$^3$) & Max. drawdown (h) & All shapes \\\midrule
__SENSITIVITYROWS__
\bottomrule\end{tabular}\end{center}
These are illustrative parameter bounds, not measured local uncertainty ranges. A sensitivity failure limits the recommendation's robustness; it does not retroactively change the nominal selection rules.
\newpage
\pagetitle{Recommendation, limitations, and review record}
\textbf{Conditional recommendation.} __RECOMMENDATION__ The search establishes the smallest passing \emph{tested} capacity; it is not a continuous optimization or a construction-ready design. A capacity between the tested increments has not been optimized.

\textbf{Limits of the finding.} No site survey, soils investigation, observed rainfall-runoff record or calibration is available. Synthetic depths carry no recurrence interval or location-specific regulatory meaning. CN and lag simplify parking drainage; free discharge excludes tailwater and pipe-network effects. A constant-area basin does not establish safe side slopes or retaining-wall details. There is no freeboard allowance, spillway sizing, water-quality assessment, structural design, infiltration benefit or inundation map. These exclusions constrain how the reported capacity can be interpreted.

\textbf{Reproduction.} Run \texttt{python run\_project.py} in the documented Python environment with pdfLaTeX available. All numerical inputs are local. The command verifies the model, refines the grid, regenerates saved time series, runs sensitivity, and rebuilds the dashboard, workbook, SVG/DXF drawings, figures and this six-page report. Actual runtime, machine architecture, package versions, source hashes and artifact checks are in \texttt{results/run\_manifest.json}. The study-stage runtime in this run was __RUNTIME__ s on __ARCH__.

\textbf{Assistance and actual contributions.} Codex implemented, executed, checked and documented the study from the supplied project plan. This report does not attribute model coding, manual Excel verification or CAD editing to Manasi. Her learning guide reserves three review sessions: reproduce a worked check, change an assumption and interpret the result, and inspect/edit the drawing and explain a design choice. Her own written interpretation and sign-off remain pending. Resume wording should reflect her demonstrated contribution after that review.

\textbf{Recorded findings.} The companion \texttt{FINDINGS.md} includes all selected-case metrics, failure mechanisms, sensitivity outcomes, actual execution measurements and outstanding human review. \texttt{CONTRIBUTIONS.md} records assistance explicitly.

{\footnotesize
\begin{thebibliography}{9}
__REFERENCES__
\end{thebibliography}}
\end{document}
'''
    smaller = "No feasible configuration was found; review the per-design failure table."
    if winner:
        lower = r["selection_table"][r["selection_table"].capacity_m3 < winner["capacity_m3"]]
        next_lower = lower[lower.capacity_m3 == lower.capacity_m3.max()]
        best_lower = next_lower.sort_values("worst_overflow_m3").iloc[0] if len(next_lower) else None
        same_cap = r["selection_table"][r["selection_table"].capacity_m3 == winner["capacity_m3"]]
        smaller = (f"Every lower-capacity tested design fails at least one design storm. "
                   + (f"At {best_lower.capacity_m3:g} m$^3$, even the {best_lower.outlet_side_mm:g} mm opening has "
                      f"{best_lower.worst_overflow_m3:.2f} m$^3$ worst-case overflow. " if best_lower is not None else "")
                   + f"At the selected capacity, {int(same_cap.all_design_storms_pass.sum())} of {len(same_cap)} tested openings pass all three shapes.")
    replacements = {
        "REDUCTION":f"{config['minimum_peak_reduction_pct']:g}","FRACTION":f"{100*config['drawdown_fraction']:g}",
        "DRAWDOWN":f"{config['drawdown_limit_h']:g}","RECOMMENDATION":recommendation,
        "ASSUMPTIONS":assumption_table,"SITEAREA":f"{config['parking_area_m2']+config['basin_area_m2']:g}",
        "HORIZON":f"{horizon:g}","CANDIDATES":str(len(r['selection_table'])),"EVENTS":str(len(r['baselines'])),
        "CASES":str(len(r['cases'])),"RESULTROWS":result_rows,"OFFROWS":off_rows,"SMALLER":smaller,
        "FIGUREIDENTITY":tex(figure_identity),"DESIGNRAIN":f"{config['design_rainfall_mm']:g}",
        "PARKVOLUME":f"{volume.parking_runoff_m3:.3f}","DIRECTVOLUME":f"{volume.direct_rain_m3:.3f}",
        "TOTALVOLUME":f"{volume.total_inflow_m3:.3f}","THRESHOLDMM":f"{basin_fraction_mm:.2f}",
        "TESTS":str(manifest['unit_tests_passed']),"BALANCEERROR":f"{balance_error:.3g}",
        "CONVERGENCEROWS":"\n".join(convergence_rows),"ONSETCHANGE":f"{last_conv.overflow_onset_change_s.max():.3f}",
        "SENSITIVITYROWS":sensitivity_rows,"REFERENCES":references,"RUNTIME":f"{manifest['model_runtime_s']:.2f}",
        "ARCH":tex(manifest['architecture'])}
    replacements["ABSTRACTION"] = f"{config['abstraction_ratio']:g}"
    replacements["RAINWEIGHTS"] = "; ".join(tex(label(shape)) + " $(" + ",".join(f"{w:g}" for w in weights) + ")$"
                                              for shape,weights in config["rainfall_weights"].items())
    for key,value in replacements.items(): text=text.replace(f"__{key}__", value)
    (root / "engineering_report.tex").write_text(text)
    executable = shutil.which("pdflatex") or "/Library/TeX/texbin/pdflatex"
    logs = []
    for _ in range(2):
        result = subprocess.run([executable,"-interaction=nonstopmode","-halt-on-error","engineering_report.tex"],
                                cwd=root,capture_output=True,text=True,timeout=90)
        logs.append(result.stdout + result.stderr)
        if result.returncode:
            (root / "results/report_build.log").write_text("\n".join(logs))
            raise RuntimeError("pdfLaTeX failed; see results/report_build.log")
    (root / "results/report_build.log").write_text("\n".join(logs))
    return {"pdflatex_runs":len(logs),"report_pdf_bytes":(root / "engineering_report.pdf").stat().st_size}


def write_findings(root, config, manifest):
    root = Path(root)
    r = read_results(root)
    winner = r["selection"]["selected"]
    case_count = len(r["cases"])
    last_conv = r["convergence"][np.isclose(r["convergence"].fine_dt_s, r["selection"]["final_dt_s"])]
    lines = ["# Findings: parking-lot stormwater detention", "",
        "Generated from saved numerical outputs. Conceptual engineering analysis completed with assistant support; Manasi's individual review and exercises remain unverified.", "",
        "## Design finding", ""]
    if winner:
        selected = r["cases"][r["cases"].design_id == winner["design_id"]]
        design = selected[np.isclose(selected.rainfall_mm, config["design_rainfall_mm"])]
        lines += [f"The smallest **tested** passing capacity is **{winner['capacity_m3']:g} m³**, with **{winner['storage_depth_m']:.2f} m** modeled depth over {config['basin_area_m2']:g} m² and a **{winner['outlet_side_mm']:g} × {winner['outlet_side_mm']:g} mm** square outlet. It passes every {config['design_rainfall_mm']:g} mm storm shape at CN {config['curve_number']:g}, lag {config['lag_min']:g} minutes, and Cd {config['discharge_coefficient']:g}.", "",
            md_table(["Storm shape", "Baseline peak (L/s)", "Detained peak (L/s)", "Reduction", "Max storage (m³)", "Overflow (m³)", "Drawdown after rain (h)"],
            [[label(row['shape']),fmt(row.baseline_peak_m3_s*1000),fmt(row.peak_downstream_m3_s*1000),f"{row.peak_reduction_pct:.2f}%",fmt(row.maximum_storage_m3),fmt(row.overflow_m3,3),fmt(row.drawdown_h_after_rain)] for _,row in design.iterrows()]), "",
            f"The drainage criterion is below {config['drawdown_fraction']*winner['capacity_m3']:.2f} m³ ({config['drawdown_fraction']*winner['storage_depth_m']*1000:.2f} mm water depth), remaining below it for the rest of the event. It is measured from rainfall end, not from peak storage. The worst case is {winner['worst_drawdown_h']:.3f} hours. Maximum design-event depth is {design.maximum_depth_m.max():.4f} m, leaving {winner['capacity_m3']-design.maximum_storage_m3.max():.3f} m³ below the nominal accounting capacity. This is not a designed freeboard allowance.", ""]
        lower = r["selection_table"][r["selection_table"].capacity_m3 < winner['capacity_m3']]
        if len(lower):
            cap = lower.capacity_m3.max()
            best = lower[lower.capacity_m3 == cap].sort_values("worst_overflow_m3").iloc[0]
            lines += [f"Every lower-capacity candidate fails at least one design shape. At {cap:g} m³, the least-overflowing tested opening ({best.outlet_side_mm:g} mm) still produces {best.worst_overflow_m3:.3f} m³ of worst-case overflow. See [the complete selection table](results/design_selection.csv).", ""]
        same = r["selection_table"][r["selection_table"].capacity_m3 == winner['capacity_m3']]
        lines += [f"At {winner['capacity_m3']:g} m³, {int(same.all_design_storms_pass.sum())} of {len(same)} openings passes all design shapes. The tie rule is lowest capacity, then shortest worst-case drawdown, then least overflow, then largest opening. Larger tested passing designs are retained in the comparison; their extra capacity is not necessary for the nominal objective.", "",
            "## Performance beyond the selected design event", "",
            md_table(["Rain (mm)", "Shape", "Peak reduction", "Overflow (m³)", "Discharged by horizon (m³)", "Residual (m³)", "Horizon (h)"],
             [[f"{row.rainfall_mm:g}", label(row['shape']), f"{max(0,row.peak_reduction_pct):.2f}%",fmt(row.overflow_m3,3),fmt(row.total_discharge_m3,3),fmt(row.residual_storage_m3,4),fmt(row.horizon_h,0)]
              for _,row in selected.iterrows()]), "",
            "The 100 mm cases exceed the selected storage substantially. The overflow belongs in downstream discharge; omitting it would create a false impression of protection. These depths have no assigned recurrence interval. No spillway hydraulics or flooding extent was modeled.", ""]
    else:
        lines += ["**The candidate search is infeasible.** No tested design passes every design-event shape. The objectives were retained, and no compliant design is claimed. Inspect `results/design_selection.csv` for individual failures.", ""]
    volume = r["baselines"][np.isclose(r["baselines"].rainfall_mm,config["design_rainfall_mm"])].iloc[0]
    lines += ["## Water balance and interpretation", "",
        f"The {config['design_rainfall_mm']:g} mm event produces {volume.parking_runoff_m3/config['parking_area_m2']*1000:.6f} mm of parking runoff, or {volume.parking_runoff_m3:.6f} m³. Direct footprint rainfall adds {volume.direct_rain_m3:.6f} m³. Each alternative receives **{volume.total_inflow_m3:.6f} m³**. The {config['parking_area_m2']+config['basin_area_m2']:g} m² study area and downstream comparison point are unchanged between alternatives.", "",
        "Controlled discharge + overflow + remaining storage equals input. Zero basin infiltration and evaporation mean the benefit is delayed timing and reduced peak flow; the model does not remove runoff volume. The low-depth outlet law drains asymptotically, so small horizon residuals are expected and explicitly counted.", "",
        md_table(["Balance", "Largest absolute error (m³)", "Largest relative error"],
            [[name,f"{value['absolute_m3']:.4e}",f"{value['relative']:.4e}"] for name,value in manifest['max_balance_errors'].items()]), "",
        "## Numerical verification", "",
        f"All {manifest['unit_tests_passed']} numerical tests passed. They cover zero rainfall, rainfall below initial abstraction (with direct footprint rain still included), CN 100, empty storage, a blocked outlet, capacity exceedance, analytical shallow drainage, pulse volume/timing/tail, and per-step continuity. See [test results](results/test_results.txt) and [independent calculations](results/independent_checks.json).", "",
        f"All {case_count} candidate cases were repeated at {', '.join(f'{v:g}' for v in manifest['tested_resolutions_s'])} seconds. Final published metrics and time series use **{manifest['final_dt_s']:g} s**. The largest final peak-flow change is **{100*last_conv.peak_downstream_m3_s_relative_change.max():.4f}%**; maximum-storage change is **{100*last_conv.maximum_storage_m3_relative_change.max():.4f}%**. Both are below 1% for the entire grid. Winner selection, event pass/fail, and overflow/no-overflow classification are stable at the final pair.", "",
        f"Final overflow-volume change is at most {last_conv.overflow_change_m3.max():.6f} m³; onset shifts by at most {last_conv.overflow_onset_change_s.max():.3f} s. Drawdown shifts by at most {last_conv.drawdown_change_s.max():.3f} s. Earlier 30/15/7.5 s results were insufficient for some overflowing alternatives, which explains the extra refinement. [All convergence checks](results/convergence.csv) are saved.", "",
        "The workbook has independent CN equations, an exact blocked-storage calculation, and 45 Excel-formula bisection iterations for a controlled-outlet step. Its formula evaluator reopens the saved workbook, evaluates every formula and verifies each cached result. Excel is set to recalculate automatically. A manual Excel session by Manasi is not claimed.", "",
        "## Sensitivity findings", ""]
    summary = sensitivity_summary(r["sensitivity"])
    lines += [md_table(["Varied parameter", "Value", "Worst reduction", "Worst overflow (m³)", "Worst drawdown (h)", "Every shape passes"],
        [[v['parameter'], f"{v['value']:g}", f"{v['minimum_peak_reduction_pct']:.2f}%",fmt(v['maximum_overflow_m3'],3),fmt(v['maximum_drawdown_h']),"Yes" if v['all_pass'] else "No"] for v in summary]), ""]
    if not r["sensitivity"].empty:
        failures = r["sensitivity"][~r["sensitivity"].all_pass]
        for _,row in failures.iterrows():
            lines += [f"**Sensitivity failure:** {row.varied_parameter} = {row.parameter_value:g}, {label(row['shape']).lower()} {row.rainfall_mm:g} mm storm: {row.peak_reduction_pct:.3f}% peak reduction and {row.overflow_m3:.3f} m³ overflow. The nominal recommendation therefore does not pass every tested uncertainty assumption.", ""]
    lines += ["Each row changes one parameter only and recomputes the matching baseline; these are not joint worst-case combinations or measured local bounds. Nominal values intentionally repeat in each parameter group.", "",
        "## Reproducibility and outputs", "",
        f"Machine: `{manifest['platform']}`, `{manifest['architecture']}`. Python: `{manifest['python'].splitlines()[0]}`. The grid contains {len(r['selection_table'])} designs, {len(r['baselines'])} storms and {case_count} routed cases; there are {manifest['sensitivity_cases']} sensitivity rows (nominal repeats included). The longest core horizon is {r['cases'].horizon_h.max():g} h, automatically extended where the 30 h initial horizon did not establish drainage.", "",
        f"Measured study-stage runtime: **{manifest['model_runtime_s']:.2f} s**. Median final-resolution case: **{manifest['median_case_runtime_s']:.4f} s**; slowest: **{manifest['max_case_runtime_s']:.4f} s**. Recorded full command runtime: **{manifest.get('total_runtime_s',0):.2f} s**. Peak Python-process memory: **{manifest.get('peak_process_memory_mib',0):.2f} MiB** (child-process memory excluded). Timing includes the actual execution on this Mac and is not a general hardware benchmark.", "",
        "Package versions, input snapshots, source hashes and timestamps are in [the run manifest](results/run_manifest.json). [Artifact checks](results/artifact_audit.json) cover saved time-series consistency, workbook formulas, embedded dashboard data, drawings and the PDF. Follow [README.md](README.md) to regenerate everything with one command.", "",
        "## Scope and unfinished human review", "",
        "The technical study, calculations, comparisons and portfolio files are assistant-generated. No survey, field calibration, return-period analysis, freeboard design, side-slope design, structural sizing, pipe-network design, tailwater analysis or water-quality benefit is established. The dimensional drawing identifies its constant-area storage idealization.", "",
        "Manasi still needs to complete the exercises and record her own interpretation in [MANASI_REVIEW.md](MANASI_REVIEW.md). Her manual Excel checks, parameter experiment, CAD edits and resume claims remain pending until she performs them. This work does not invent contributions or sign off on her behalf.", "",
        "## Sources", ""]
    for entry in json.loads((root / "results/source_inputs/sources.json").read_text()):
        lines += [f"- [{entry['title']}]({entry['url']}) — {entry['use']} Accessed {entry['accessed']}."]
    (root / "FINDINGS.md").write_text("\n".join(lines)+"\n")


def write_learning_materials(root, config, manifest):
    root = Path(root)
    r = read_results(root)
    winner = r["selection"]["selected"]
    nominal = r["baselines"][np.isclose(r["baselines"].rainfall_mm,config["design_rainfall_mm"])].iloc[0]
    selected_text = (f"{winner['capacity_m3']:g} m³, {winner['storage_depth_m']:.2f} m deep, with a {winner['outlet_side_mm']:g} mm square opening" if winner else "No tested design meets the targets")
    readme = f'''# Stormwater detention modeling and design study

A completed, assistant-generated conceptual study of a hypothetical parking lot.
The nominal selection is **{selected_text}**. Read [FINDINGS.md](FINDINGS.md) for
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
| [stormwater_dashboard.html](stormwater_dashboard.html) | Open directly in a browser; all {len(r['cases'])} cases and baselines are embedded. No server or internet required. |
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
{manifest['final_dt_s']:g} s after testing {', '.join(f'{v:g}' for v in manifest['tested_resolutions_s'])} s.
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
'''
    (root / "README.md").write_text(readme)
    retention = 25400 / config['curve_number'] - 254
    guide = f'''# Learning guide

This guide uses the actual saved study. The technical implementation was generated
with Codex assistance. Use `MANASI_REVIEW.md` to document what you personally check,
change and explain. Allow three 60–90 minute sessions, adjusted to your pace.

## Session 1: rainfall becomes runoff

Open the dashboard with {config['design_rainfall_mm']:g} mm rainfall, then switch among
the three shapes. A **hyetograph** shows rainfall intensity; a **hydrograph** shows
flow over time. Millimetres describe a depth, mm/hour a rate, m³ a volume and
m³/s a volumetric flow. A high rainfall block does not make the downstream peak
instantaneous because runoff takes time to arrive.

The curve number is a compact event-loss assumption. Here CN {config['curve_number']:g}
gives S = 25400/CN − 254 = {retention:.6f} mm and Ia = {config['abstraction_ratio']:g}S
= {config['abstraction_ratio']*retention:.6f} mm. Substitute {config['design_rainfall_mm']:g} mm
of cumulative rain in (P − Ia)²/(P − Ia + S). The result is
{nominal.parking_runoff_m3/config['parking_area_m2']*1000:.6f} mm of excess depth,
or {nominal.parking_runoff_m3:.6f} m³ over {config['parking_area_m2']:g} m².
Direct rainfall over the {config['basin_area_m2']:g} m² footprint contributes
{nominal.direct_rain_m3:.6f} m³. Total input is {nominal.total_inflow_m3:.6f} m³.

Reproduce this with a calculator and the workbook's `Runoff checks` sheet.
Column H is a Python reference; columns B–G are formulas you can inspect.
Initial abstraction is applied once to cumulative rain, not subtracted again
at each time step. For CN 100, S and Ia are zero and runoff equals rainfall.

The **unit hydrograph** is the timing response to a unit amount of runoff.
In `inputs/scs_dimensionless_uh.csv`, both columns are ratios. A lag of
{config['lag_min']:g} minutes controls response timing; it is not another loss.
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

Open the default selected design: **{selected_text}**. Its constant-area model
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
'''
    (root / "LEARNING_GUIDE.md").write_text(guide)
    if not (root / "MANASI_REVIEW.md").exists():
        (root / "MANASI_REVIEW.md").write_text('''# Manasi's personal review — pending

This file is reserved for Manasi's own work. The assistant does not complete or
sign it on her behalf. Regeneration preserves this file.

- [ ] Reproduced the runoff-volume calculation with a calculator and Excel.
- [ ] Explained the equal site area and direct footprint rainfall.
- [ ] Predicted and ran one parameter experiment in a separate output directory.
- [ ] Compared peaks, storage, overflow, drawdown and total volume.
- [ ] Inspected the conceptual drawing and recorded any actual CAD edits.
- [ ] Read the convergence and sensitivity findings.
- [ ] Wrote an independent design interpretation and reviewed assistance attribution.

## Worked check

Date, calculations and interpretation:

## Parameter experiment

Changed input and reason:

Prediction before running:

Command and output directory:

Observed results and explanation:

## Drawing review

Application used and actual changes, if any:

## My interpretation (150–250 words)

## Contribution record and review date

Own work completed:

Assistance used:

Reviewed by / date:
''')
    if not (root / "CONTRIBUTIONS.md").exists():
        (root / "CONTRIBUTIONS.md").write_text('''# Contribution and assistance record

The supplied `PROJECT_PLAN.md` defines the project. Codex implemented the
numerical model and automated tests, ran the grid and sensitivity analyses,
created the workbook, dashboard, figures, conceptual SVG/DXF drawings and
LaTeX report, and wrote findings and learning materials.

Manasi's personal coding, manual spreadsheet review, parameter experiment,
CAD edits and written interpretation have not been observed or verified.
`MANASI_REVIEW.md` is the place to record these contributions after she performs
them. No field data, site survey or calibration was supplied.

The outputs are a completed assistant-generated technical study. The hands-on
learning and individual portfolio sign-off remain pending. Generated work
should not be presented as independently authored or manually verified by
Manasi until her actual contribution is documented.
''')
