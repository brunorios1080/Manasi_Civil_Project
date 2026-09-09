#!/usr/bin/env python3
"""Regenerate the complete offline stormwater study from local source inputs."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import pandas as pd

from stormwater.hydrology import load_ordinates
from stormwater.study import (compare_resolutions, independent_checks, run_grid,
                              run_sensitivity, select_design, write_json)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_config(c):
    for key in ("parking_area_m2", "basin_area_m2", "lag_min", "rainfall_duration_min",
                "time_step_s", "horizon_h", "max_horizon_h", "gravity_m_s2"):
        if not isinstance(c[key], (float, int)) or not np.isfinite(c[key]) or c[key] <= 0:
            raise ValueError(f"{key} must be a positive finite number")
    if not 0 < c["curve_number"] <= 100 or c["discharge_coefficient"] <= 0:
        raise ValueError("Core scenarios require CN in (0,100] and an open outlet")
    for key in ("initial_storage_m3", "basin_infiltration_mm_h", "evaporation_mm_h"):
        if c[key] != 0:
            raise ValueError(f"{key} must be zero in this event-only core study")
    if c["max_horizon_h"] < c["horizon_h"]:
        raise ValueError("Maximum horizon cannot be shorter than initial horizon")
    if c["design_rainfall_mm"] not in c["rainfall_depths_mm"]:
        raise ValueError("Design rainfall must occur in the tested rain depths")
    for key in ("storage_depths_m", "outlet_sides_mm", "rainfall_depths_mm"):
        if not c[key] or len(set(c[key])) != len(c[key]) or any(v <= 0 for v in c[key]):
            raise ValueError(f"{key} must contain unique positive values")
    for area, length, width in (("parking_area_m2", "parking_length_m", "parking_width_m"),
                                ("basin_area_m2", "basin_length_m", "basin_width_m")):
        if not np.isclose(c[area], c[length] * c[width]):
            raise ValueError(f"{area} must match the drawing dimensions")
    if not 0 < c["drawdown_fraction"] < 1:
        raise ValueError("Drawdown fraction must lie strictly between zero and one")


def run_tests(output):
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (output / "test_results.txt").write_text(stream.getvalue())
    print(f"Verification tests: {result.testsRun} run; success={result.wasSuccessful()}", flush=True)
    if not result.wasSuccessful():
        print(stream.getvalue())
        raise RuntimeError("Model verification failed")
    return result.testsRun


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "inputs/config.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--model-only", action="store_true", help="Run verification and study, skip portfolio outputs")
    mode.add_argument("--artifacts-only", action="store_true", help="Rebuild portfolio outputs from matching saved results")
    args = parser.parse_args()
    started = time.perf_counter()
    output_root = args.output_dir.resolve()
    results = output_root / "results"
    results.mkdir(parents=True, exist_ok=True)
    config = json.loads(args.config.read_text())
    validate_config(config)
    input_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    if args.artifacts_only:
        manifest = json.loads((results / "run_manifest.json").read_text())
        if manifest["config_sha256"] != input_hash:
            raise ValueError("Saved results have different inputs; perform a full model run")
    else:
        manifest = {"started_utc": datetime.now(timezone.utc).isoformat(), "status": "running",
                    "config_sha256": input_hash, "python": sys.version,
                    "platform": platform.platform(), "architecture": platform.machine(),
                    "executable": sys.executable, "command": sys.argv,
                    "packages": {p: importlib.metadata.version(p) for p in
                        ("numpy", "pandas", "scipy", "matplotlib", "plotly", "openpyxl", "xlsxwriter", "PyMuPDF")}}
        write_json(results / "run_manifest.json", manifest)
        write_json(results / "config_used.json", config)
        source_dir = results / "source_inputs"
        source_dir.mkdir(exist_ok=True)
        for name in ("scs_dimensionless_uh.csv", "sources.json"):
            shutil.copyfile(ROOT / "inputs" / name, source_dir / name)
        ordinates = load_ordinates(source_dir / "scs_dimensionless_uh.csv")
        manifest["unit_tests_passed"] = run_tests(results)
        model_start = time.perf_counter()
        resolutions, comparisons, previous, previous_winner = [], [], None, None
        dt = config["time_step_s"]
        final_grid = final_baselines = final_winner = selection_table = None
        for refinement in range(6):
            print(f"Running complete candidate grid at {dt:g} seconds", flush=True)
            grid, baselines = run_grid(config, ordinates, dt)
            grid.to_csv(results / f"cases_dt{dt:g}s.csv", index=False)
            baselines.to_csv(results / f"baselines_dt{dt:g}s.csv", index=False)
            winner, selection = select_design(grid, config)
            resolutions.append(dt)
            if previous is not None:
                comparison = compare_resolutions(previous, grid, config)
                comparisons.append(comparison)
                same_winner = (winner or {}).get("design_id") == (previous_winner or {}).get("design_id")
                converged = (comparison.peak_storage_converged.all()
                             and comparison.acceptance_stable.all()
                             and comparison.overflow_classification_stable.all() and same_winner)
                print(f"  maximum peak change: {100*comparison.peak_downstream_m3_s_relative_change.max():.4f}%; "
                      f"maximum storage change: {100*comparison.maximum_storage_m3_relative_change.max():.4f}%; "
                      f"all classifications stable: {comparison.acceptance_stable.all()}", flush=True)
                if refinement >= 2 and converged:
                    final_grid, final_baselines, final_winner, selection_table = grid, baselines, winner, selection
                    break
            previous, previous_winner = grid, winner
            dt /= 2
        if final_grid is None:
            raise RuntimeError("Convergence or design stability unresolved after six resolutions")
        # Persist every final series using exactly the published resolution.
        print("Saving final time series", flush=True)
        saved_grid, saved_baselines = run_grid(config, ordinates, resolutions[-1], results / "timeseries")
        numeric_cols = [c for c in final_grid.select_dtypes(include="number").columns if c != "simulation_runtime_s"]
        np.testing.assert_allclose(saved_grid[numeric_cols], final_grid[numeric_cols], rtol=1e-12, atol=1e-12, equal_nan=True)
        final_grid = saved_grid
        final_grid.to_csv(results / "scenarios.csv", index=False)
        final_baselines.to_csv(results / "baselines.csv", index=False)
        selection_table.to_csv(results / "design_selection.csv", index=False)
        pd.concat(comparisons, ignore_index=True).to_csv(results / "convergence.csv", index=False)
        write_json(results / "selection.json", {"selected": final_winner,
            "design_rainfall_mm": config["design_rainfall_mm"], "final_dt_s": resolutions[-1],
            "tie_break": "Lowest capacity; then shortest worst-case drawdown across design storm shapes; then least overflow; then largest opening.",
            "status": "feasible" if final_winner else "infeasible"})
        reps = config["storage_depths_m"]
        representative_depths = [reps[min(1,len(reps)-1)], reps[min(3,len(reps)-1)], reps[-1]]
        representative_side = min(config["outlet_sides_mm"], key=lambda v: abs(v - 80))
        final_grid[final_grid.storage_depth_m.isin(representative_depths) &
                   (final_grid.outlet_side_mm == representative_side)].to_csv(results / "representative_cases.csv", index=False)
        sensitivity = run_sensitivity(config, ordinates, final_winner, resolutions[-1], results)
        sensitivity.to_csv(results / "sensitivity.csv", index=False)
        checks = independent_checks(config, ordinates)
        write_json(results / "independent_checks.json", checks)
        pd.DataFrame(checks["outlet_checks"]).to_csv(results / "outlet_checks.csv", index=False)
        all_balances = pd.concat([final_grid, sensitivity], ignore_index=True)
        max_errors = {}
        for metric in ("runoff_generation_error_m3", "transform_error_m3", "routing_balance_error_m3"):
            abs_error = all_balances[metric].abs()
            scale = all_balances.total_inflow_m3
            allowed = config["balance_absolute_tolerance_m3"] + config["balance_relative_tolerance"] * scale
            if not (abs_error <= allowed).all():
                raise RuntimeError(f"Water balance failed: {metric}")
            max_errors[metric] = {"absolute_m3": float(abs_error.max()),
                                  "relative": float((abs_error / scale).max())}
        manifest.update({"model_runtime_s": time.perf_counter() - model_start,
            "tested_resolutions_s": resolutions, "final_dt_s": resolutions[-1],
            "candidate_event_cases": len(final_grid), "baseline_events": len(final_baselines),
            "sensitivity_cases": len(sensitivity), "max_balance_errors": max_errors,
            "median_case_runtime_s": float(final_grid.simulation_runtime_s.median()),
            "max_case_runtime_s": float(final_grid.simulation_runtime_s.max()),
            "model_status": "verified", "status": "model_complete"})
        write_json(results / "run_manifest.json", manifest)
    if not args.model_only:
        print("Building dashboard, workbook, drawings, report, and learning materials", flush=True)
        from stormwater.deliverables import build_deliverables, audit_deliverables
        artifact_start = time.perf_counter()
        build_deliverables(ROOT, output_root, config, manifest)
        audit = audit_deliverables(output_root, config, manifest)
        write_json(results / "artifact_audit.json", audit)
        if not audit["passed"]:
            raise RuntimeError("Artifact verification failed; see results/artifact_audit.json")
        manifest["artifact_runtime_s"] = time.perf_counter() - artifact_start
        manifest["status"] = "complete"
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    manifest["peak_process_memory_mib"] = peak_rss / (1024**2 if sys.platform == "darwin" else 1024)
    if args.artifacts_only:
        manifest["last_artifact_rebuild_runtime_s"] = time.perf_counter() - started
    else:
        manifest["total_runtime_s"] = time.perf_counter() - started
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["source_hashes"] = {str(p.relative_to(ROOT)): sha256(p) for pattern in
        ("stormwater/*.py", "tests/*.py", "inputs/*", "run_project.py") for p in ROOT.glob(pattern) if p.is_file()}
    write_json(results / "run_manifest.json", manifest)
    if not args.model_only:
        from stormwater.deliverables import write_findings
        write_findings(output_root, config, manifest)
    print(f"Finished: {manifest['status']}; this command took {time.perf_counter()-started:.2f} s", flush=True)
    selected = json.loads((results / "selection.json").read_text())["selected"]
    print(json.dumps(selected, indent=2), flush=True)


if __name__ == "__main__":
    main()
