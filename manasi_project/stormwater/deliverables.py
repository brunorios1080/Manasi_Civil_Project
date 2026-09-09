"""Build and verify every requested project artifact from saved outputs."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import fitz
import numpy as np
import pandas as pd

from .dashboard import build_dashboard
from .figures import build_drawings, build_figures
from .reporting import (build_report, read_results, write_findings,
                        write_learning_materials)
from .study import write_json
from .workbook import audit_workbook, build_workbook


def build_deliverables(source_root, output_root, config, manifest):
    root = Path(output_root)
    results = read_results(root)
    kwargs = [root, config, results["cases"], results["selection"], results["sensitivity"]]
    print("  Scientific figures", flush=True)
    metadata = {"figures": build_figures(*kwargs)}
    print("  Dimensioned SVG, PDF, and DXF", flush=True)
    metadata["drawings"] = build_drawings(root, config, results["cases"], results["selection"])
    print("  Offline interactive dashboard", flush=True)
    metadata["dashboard"] = build_dashboard(root, config, results["cases"], results["baselines"], results["selection"])
    print("  Independent Excel formulas and charts", flush=True)
    metadata["workbook"] = build_workbook(root, config, results["cases"], results["baselines"], results["selection"], results["sensitivity"])
    print("  LaTeX report", flush=True)
    metadata["report"] = build_report(root, config, manifest)
    write_learning_materials(root, config, manifest)
    write_findings(root, config, manifest)
    write_json(root / "results/artifact_build.json", metadata)


def audit_deliverables(root, config, manifest):
    root = Path(root)
    errors = []
    results = read_results(root)
    cases = results["cases"]
    expected_events = len(config["rainfall_depths_mm"]) * len(config["rainfall_weights"])
    expected_cases = expected_events * len(config["storage_depths_m"]) * len(config["outlet_sides_mm"])
    if len(cases) != expected_cases or cases.duplicated(["event_id", "design_id"]).any():
        errors.append("Candidate case count or uniqueness mismatch")
    series_checked = 0
    largest_series_residual = 0.0
    for _, row in cases.iterrows():
        path = root / "results/timeseries" / f"{row.event_id}__{row.design_id}.npz"
        with np.load(path) as data:
            storage = data["storage_m3"]
            qout = data["controlled_m3_s"]
            over = data["overflow_m3_s"]
            inputs = data["parking_inflow_m3"] + data["direct_rain_m3"]
            if len(storage) != len(inputs) + 1 or len(data["time_edges_s"]) != len(storage):
                errors.append(f"Array length mismatch: {path.name}")
            residual = float(abs(inputs.sum() - (qout.sum()+over.sum()) * row.dt_s - storage[-1]))
            largest_series_residual = max(largest_series_residual, residual)
            checks = [
                np.isclose(data["rain_mm"].sum(), row.rainfall_mm, atol=1e-10, rtol=1e-12),
                np.isclose(inputs.sum(), row.total_inflow_m3, atol=1e-8, rtol=1e-12),
                np.isclose(storage.max(), row.maximum_storage_m3, atol=1e-8, rtol=1e-12),
                np.isclose((qout+over).max(), row.peak_downstream_m3_s, atol=1e-10, rtol=1e-10),
                np.isclose(over.sum()*row.dt_s, row.overflow_m3, atol=1e-8, rtol=1e-10),
                np.isclose(storage[-1], row.residual_storage_m3, atol=1e-8, rtol=1e-10),
                storage.min() >= 0, storage.max() <= row.capacity_m3 + 1e-8,
                qout.min() >= 0, over.min() >= 0,
                residual < config["balance_absolute_tolerance_m3"] + config["balance_relative_tolerance"]*row.total_inflow_m3,
            ]
            if not all(checks): errors.append(f"Saved series disagrees with metrics: {path.name}")
            series_checked += 1
    workbook = audit_workbook(root / "stormwater_calculations.xlsx")
    errors.extend(workbook["errors"])
    html = (root / "stormwater_dashboard.html").read_text()
    match = re.search(r'<script id="project-data" type="application/json">(.*?)</script>',html,re.S)
    payload = json.loads(match.group(1)) if match else None
    if payload is None or len(payload["cases"]) != expected_cases or len(payload["events"]) != expected_events:
        errors.append("Embedded dashboard data count mismatch")
    if re.search(r'<(?:script|link|img)\b[^>]+(?:src|href)=["\']https?://', html, flags=re.I):
        errors.append("Dashboard has an external rendering dependency")
    dashboard_checked = 0
    for _, row in cases.iterrows():
        key = f"{row.event_id}__{row.design_id}"
        entry = payload["cases"][key]
        if not np.isclose(entry["metrics"]["peak_downstream_m3_s"],row.peak_downstream_m3_s,rtol=1e-9,atol=1e-10):
            errors.append(f"Dashboard metric mismatch: {key}")
        sampled_peak = max(q + o for q,o in zip(entry["series"]["controlled_l_s"],entry["series"]["overflow_l_s"]))
        if not np.isclose(sampled_peak,row.peak_downstream_m3_s*1000,rtol=1e-8,atol=1e-6):
            errors.append(f"Dashboard omitted peak: {key}")
        dashboard_checked += 1
    svg = ET.parse(root / "site_plan.svg")
    if not svg.getroot().tag.endswith("svg"):
        errors.append("Drawing is not valid SVG")
    dxf_lines = (root / "site_plan.dxf").read_text().splitlines()
    if len(dxf_lines) % 2 or dxf_lines[-2:] != ["0", "EOF"]:
        errors.append("Malformed DXF record structure")
    pairs = list(zip(dxf_lines[0::2],dxf_lines[1::2]))
    dxf_entity_count = sum(code == "0" and value in ("LINE", "TEXT") for code,value in pairs)
    if dxf_entity_count < 30 or ("1","AC1009") not in pairs:
        errors.append("DXF primitives/header missing")
    with fitz.open(root / "engineering_report.pdf") as pdf:
        page_count = len(pdf)
        pdf_text = "\n".join(page.get_text() for page in pdf)
        if page_count != 6:
            errors.append(f"Report should have six pages, found {page_count}")
        for i,page in enumerate(pdf):
            for block in page.get_text("blocks"):
                if block[0] < -1 or block[1] < -1 or block[2] > page.rect.width+1 or block[3] > page.rect.height+1:
                    errors.append(f"Report content extends off page {i+1}")
        winner = results["selection"]["selected"]
        if winner and (f"{winner['worst_peak_reduction_pct']:.2f}" not in pdf_text or f"{winner['worst_drawdown_h']:.2f}" not in pdf_text):
            errors.append("Report recommendation metrics missing")
        if "__" in (root / "engineering_report.tex").read_text():
            errors.append("Unresolved report template token")
    required = ["run_project.py", "stormwater_dashboard.html", "stormwater_calculations.xlsx",
                "site_plan.svg", "site_plan.dxf", "engineering_report.tex", "engineering_report.pdf",
                "LEARNING_GUIDE.md", "README.md", "FINDINGS.md", "CONTRIBUTIONS.md", "MANASI_REVIEW.md"]
    # A separate experiment output intentionally uses the original source runner.
    for name in required:
        if name == "run_project.py" and root != Path(__file__).resolve().parents[1]: continue
        if not (root / name).is_file() or (root / name).stat().st_size == 0:
            errors.append(f"Missing deliverable: {name}")
    return {"passed":not errors,"errors":errors,"saved_time_series_checked":series_checked,
        "largest_saved_series_balance_error_m3":largest_series_residual,
        "workbook":workbook,"dashboard_cases_checked":dashboard_checked,
        "dashboard_has_external_rendering_dependencies":False,
        "dxf_entity_count":dxf_entity_count,"report_pages":page_count,
        "note":"This automatic audit checks numerical artifacts and document structure. Separate browser and visual inspection are recorded in results/visual_review.json when performed."}
